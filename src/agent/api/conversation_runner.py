import asyncio
import datetime as dt
import logging
from typing import Any, Dict, cast
from uuid import uuid4

from fastapi import HTTPException

from langchain.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, StreamPart
from pydantic import TypeAdapter
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import agent.db.models as db_models
import agent.db.utils as db_utils
from agent.api.conversation_models import (
    CompletionResponseError,
    CompletionResponseHistory,
    CompletionUserMessage,
)
from agent.api.conversation_service import delete_conversation as delete_conversation_record
from agent.api.title_generator import ConversationTitleGenerator
from agent.core.state import ResumePayload
from agent.file_utils.utils import (
    PendingMessageAttachmentRef,
    bind_pending_message_attachments,
    load_attachment_content,
)
from agent.parser import AnthropicEventParser
from agent.utils.exception import is_langchain_network_failure

log = logging.getLogger(__name__)
message_type_adapter = TypeAdapter(AnyMessage)
TITLE_GENERATION_TIMEOUT_SECONDS = 60
MAIN_MODEL_NODE_NAME = "chat"
TOOL_NODE_NAME = "tool_node"
MCP_TOOL_NODE_NAME = "mcp_tool_node"
TOOL_NODE_NAMES = {TOOL_NODE_NAME, MCP_TOOL_NODE_NAME}
USER_INPUT_NODE_NAME = "user_input"

class _ConversationJobState:
    def __init__(self):
        self.history = []
        self.cond = asyncio.Condition()
        self.task: asyncio.Task[None] | None = None
        self.run_task: asyncio.Task[Any] | None = None
        self.delete_requested = False
        self.user_message_id = ""


class TitleTaskManager:
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory
        self.title_generator = ConversationTitleGenerator()
        self._tasks: Dict[str, asyncio.Task[None]] = {}

    def request_title_generation(
        self,
        conversation_id: str,
        current_title: str | None,
        user_message: str,
    ):
        if not self.title_generator.should_generate_title(current_title):
            return

        title_input = self.title_generator.build_title_input(user_message)
        if not title_input:
            return

        current_task = self._tasks.get(conversation_id)
        if current_task and not current_task.done():
            return

        self._tasks[conversation_id] = asyncio.create_task(
            self._run_title_task(conversation_id, title_input)
        )

    def _cleanup_task(self, conversation_id: str):
        current_task = asyncio.current_task()
        if self._tasks.get(conversation_id) is current_task:
            self._tasks.pop(conversation_id, None)

    def cancel(self, conversation_id: str):
        task = self._tasks.pop(conversation_id, None)
        if task and not task.done():
            task.cancel()

    async def _conversation_needs_title(self, conversation_id: str) -> bool:
        conversation = await db_utils.db_get_conversation(self.session_factory, conversation_id)
        return bool(
            conversation and self.title_generator.should_generate_title(conversation.title)
        )

    async def _run_title_task(self, conversation_id: str, title_input: str):
        try:
            title = await asyncio.wait_for(
                self.title_generator.generate(title_input),
                timeout=TITLE_GENERATION_TIMEOUT_SECONDS,
            )
            if not title:
                return

            if not await self._conversation_needs_title(conversation_id):
                return

            await db_utils.db_update_conversation_title(
                self.session_factory,
                conversation_id,
                title,
            )
        except asyncio.TimeoutError:
            log.warning(
                "Conversation title generation timed out after %ss: conversation_id=%s",
                TITLE_GENERATION_TIMEOUT_SECONDS,
                conversation_id,
            )
        except Exception as exc:
            log.exception(
                "Failed to update conversation title: conversation_id=%s, error=%s",
                conversation_id,
                exc,
            )
        finally:
            self._cleanup_task(conversation_id)
        
class ConversationRunner:
    def __init__(self, graph, session_factory : async_sessionmaker):
        self._conversation_jobs: Dict[str, _ConversationJobState] = {}
        self.graph = graph
        self.session_factory = session_factory
        self.parser = AnthropicEventParser() # TODO: select parser based on model type
        
        self.title_task_manager = TitleTaskManager(self.session_factory)
    
    def is_running(self, conversation_id: str) -> bool:
        return conversation_id in self._conversation_jobs
    
    async def run(self, conversation_id : str, user_message : str, restart_message_id: str | None = None, attachments: list[str] = []): # remove need_history and related logic
        if not user_message and not attachments:
            return
        
        if conversation_id not in self._conversation_jobs:
            job = _ConversationJobState()
            job.run_task = asyncio.current_task()
            self._conversation_jobs[conversation_id] = job
        else:
            raise ValueError(f"Conversation {conversation_id} is already running")
        
        try:
            async with self.session_factory() as session:
                session : AsyncSession
                conversation_row = await session.execute(
                    select(db_models.Conversation).where(db_models.Conversation.id == conversation_id)
                )
                conversation = conversation_row.scalars().first()
                if not conversation:
                    raise ValueError(f"Conversation {conversation_id} not found in database")
                conversation.time_last_used = dt.datetime.now(dt.timezone.utc)
                await session.commit()

            resume_checkpoint_id: str | None = None
            fallback_checkpoint_id: str | None = None
            if restart_message_id:
                async with self.session_factory() as session:
                    session : AsyncSession
                    async with session.begin():
                        restart_message = (await session.execute(
                            select(db_models.Message)
                                .where(db_models.Message.conversation_id == conversation_id)
                                .where(db_models.Message.id == restart_message_id)
                            )).scalar()
                        if restart_message is None:
                            raise ValueError(f"Restart message {restart_message_id} not found in conversation {conversation_id}")

                        previous_checkpoint_message = (await session.execute(
                            select(db_models.Message)
                                .where(db_models.Message.conversation_id == conversation_id)
                                .where(db_models.Message.seq < restart_message.seq)
                                .where(db_models.Message.checkpoint_id.is_not(None))
                                .order_by(db_models.Message.seq.desc())
                                .limit(1)
                        )).scalar()

                        resume_checkpoint_id = restart_message.checkpoint_id
                        fallback_checkpoint_id = (
                            previous_checkpoint_message.checkpoint_id
                            if previous_checkpoint_message is not None
                            else None
                        )

                        # erase resume_message and everything after it
                        await session.execute(
                            delete(db_models.Message)
                                .where(db_models.Message.conversation_id == conversation_id)
                                .where(db_models.Message.seq >= restart_message.seq)
                        )

                if resume_checkpoint_id:
                    conn = self.graph.checkpointer.conn
                    await conn.execute(
                        "DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_id >= ?",
                        (conversation_id, resume_checkpoint_id)
                    )
                    await conn.execute(
                        "DELETE FROM writes WHERE thread_id = ? AND checkpoint_id >= ?",
                        (conversation_id, resume_checkpoint_id)
                    )
                elif fallback_checkpoint_id:
                    conn = self.graph.checkpointer.conn
                    await conn.execute(
                        "DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_id > ?",
                        (conversation_id, fallback_checkpoint_id)
                    )
                    await conn.execute(
                        "DELETE FROM writes WHERE thread_id = ? AND checkpoint_id > ?",
                        (conversation_id, fallback_checkpoint_id)
                    )
                else:
                    await self.graph.checkpointer.adelete_thread(conversation_id)
            
            config : RunnableConfig = {
                "configurable": {
                    "thread_id": conversation_id
                }
            }

            user_message_id = str(uuid4())
            job = self._conversation_jobs[conversation_id]
            job.user_message_id = user_message_id
            bound_attachments: list[PendingMessageAttachmentRef] = []
            attachment_ids: list[str] = []
            human_message = HumanMessage(role="user", content=user_message)
            
            async def _ensure_thread_waiting_for_resume():
                needs_prime = True
                try:
                    snapshot = await self.graph.aget_state(config)
                    needs_prime = len(snapshot.next) == 0
                except Exception:
                    needs_prime = True

                if needs_prime:
                    await self.graph.ainvoke({}, config, version="v2")

            async def _persist_stream_message(message: AnyMessage) -> str | None:
                if isinstance(message, HumanMessage):
                    return await db_utils.db_update_message(
                        self.session_factory,
                        conversation_id=conversation_id,
                        message_id=user_message_id,
                        langchain_id=message.id,
                        content=human_message.model_dump_json(),
                        attachments=attachment_ids,
                    )

                if isinstance(message, AIMessage):
                    if not message.id:
                        return None
                    return await db_utils.db_update_message(
                        self.session_factory,
                        conversation_id=conversation_id,
                        message_id=None,
                        langchain_id=message.id,
                        content=message.model_dump_json(),
                        attachments=[],
                    )

                return None

            async def _backfill_root_checkpoint_messages(checkpoint_id: str):
                try:
                    checkpoint_snapshot = await self.graph.aget_state({
                        "configurable": {
                            "thread_id": conversation_id,
                            "checkpoint_id": checkpoint_id,
                        }
                    })
                    checkpoint_values = cast(dict[str, Any], checkpoint_snapshot.values or {})
                    checkpoint_messages = cast(list[AnyMessage], checkpoint_values.get("messages", []))
                    checkpoint_langchain_ids: list[str] = []

                    for checkpoint_message in checkpoint_messages:
                        if isinstance(checkpoint_message, ToolMessage):
                            if checkpoint_message.tool_call_id:
                                checkpoint_langchain_ids.append(checkpoint_message.tool_call_id)
                            continue
                        if isinstance(checkpoint_message, (HumanMessage, AIMessage)) and checkpoint_message.id:
                            checkpoint_langchain_ids.append(checkpoint_message.id)

                    pending_messages = await db_utils.db_get_pending_messages_by_langchain_ids(
                        self.session_factory,
                        conversation_id,
                        checkpoint_langchain_ids,
                    )
                    message_ids_to_finalize: list[str] = []
                    for langchain_id in checkpoint_langchain_ids:
                        message_row = pending_messages.get(langchain_id)
                        if message_row is not None:
                            message_ids_to_finalize.append(message_row.id)

                    if message_ids_to_finalize:
                        await db_utils.db_set_message_checkpoints(
                            self.session_factory,
                            message_ids_to_finalize,
                            checkpoint_id,
                        )
                except Exception as exc:
                    log.exception(
                        "Failed to backfill message checkpoints: conversation_id=%s, checkpoint_id=%s, error=%s",
                        conversation_id,
                        checkpoint_id,
                        exc,
                    )

            await _persist_stream_message(human_message)
            if attachments:
                try:
                    bound_attachments = await bind_pending_message_attachments(
                        self.session_factory,
                        user_message_id,
                        attachments,
                    )
                    attachment_ids = [attachment.attachment_id for attachment in bound_attachments]
                except HTTPException as exc:
                    raise HTTPException(status_code=exc.status_code, detail=exc.detail)

            attachment_content = ""
            if bound_attachments:
                try:
                    for i, attachment in enumerate(bound_attachments):
                        content, attachment_name = await load_attachment_content(self.session_factory, attachment.attachment_id)
                        display_name = attachment.name or attachment_name
                        attachment_content += f"Attachment {i + 1} [{display_name}]:\n{content}\n\n"
                except HTTPException as exc:
                    raise HTTPException(status_code=exc.status_code, detail=exc.detail)
            
            resume_payload : ResumePayload = {
                "user_input": user_message,
                "attachment_content": attachment_content
            }
            
            await _ensure_thread_waiting_for_resume()
            self.title_task_manager.request_title_generation(
                conversation_id,
                conversation.title,
                user_message,
            )

            gen = self.graph.astream(
                Command(resume=resume_payload),
                config,
                version="v2",
                stream_mode=["messages","checkpoints","updates", "values"]
            )

            async def _persist_partial_ai_message(current_message: AnyMessage | None):
                if not isinstance(current_message, AIMessage):
                    return

                try:
                    message_row = await db_utils.db_get_message_by_langchain_id(
                        self.session_factory,
                        conversation_id=conversation_id,
                        langchain_id=current_message.id
                    )
                    if message_row and message_row.checkpoint_id:
                        return

                    new_config = await self.graph.aupdate_state(
                        config,
                        {"messages": [current_message]}
                    )
                    checkpoint = new_config["configurable"]["checkpoint_id"]
                    await db_utils.db_update_message(
                        self.session_factory,
                        conversation_id=conversation_id,
                        message_id=None,
                        langchain_id=current_message.id,
                        content=current_message.model_dump_json(),
                        attachments=[],
                        checkpoint_id=checkpoint
                    )
                except Exception as exc:
                    log.exception(
                        "Failed to persist partial assistant message: conversation_id=%s, error=%s",
                        conversation_id,
                        exc,
                    )

        except asyncio.CancelledError:
            job = self._conversation_jobs.pop(conversation_id, None)
            if job is not None:
                async with job.cond:
                    job.cond.notify_all()
            raise
        except Exception:
            self._conversation_jobs.pop(conversation_id, None)
            raise
                
        async def _run(job: _ConversationJobState):
            current_message: AnyMessage | None = None
            current_message_node: str | None = None
                        
            try:
                async for event in gen:
                    event: StreamPart
                    log.debug("Received stream event: %s", event)
                    deltas = []
                    if event["type"] == "checkpoints":
                        checkpoint_payload = cast(dict[str, Any], event["data"])
                        checkpoint_config = cast(dict[str, Any], checkpoint_payload.get("config", {}))
                        checkpoint_runtime = cast(dict[str, Any], checkpoint_config.get("configurable", {}))
                        checkpoint = checkpoint_runtime.get("checkpoint_id")
                        checkpoint_ns = checkpoint_runtime.get("checkpoint_ns", "")
                        if checkpoint and not checkpoint_ns:
                            await _backfill_root_checkpoint_messages(checkpoint)
                    elif event["type"] == "messages":
                        message_data = cast(tuple[AnyMessage, dict[str, Any]], event["data"])
                        message_chunk, message_meta = message_data
                        node_name = str(message_meta.get("langgraph_node", ""))
                        if current_message_node != node_name:
                            current_message = None
                        current_message_node = node_name
                        current_message = current_message + message_chunk if current_message else message_chunk

                        if isinstance(current_message, HumanMessage):
                            if node_name != USER_INPUT_NODE_NAME:
                                continue
                            await _persist_stream_message(current_message)
                            continue # persist raw user message, not the injected attachment content

                        if isinstance(current_message, AIMessage):
                            if node_name != MAIN_MODEL_NODE_NAME:
                                continue
                            message_uuid = await _persist_stream_message(current_message)
                            if message_uuid is None:
                                continue
                            deltas = self.parser.parse_event(event, message_uuid)
                        
                        if isinstance(current_message, ToolMessage):
                            if node_name not in TOOL_NODE_NAMES:
                                continue
                            tool_call_request_message = await db_utils.db_get_message_by_langchain_id(
                                self.session_factory,
                                conversation_id=conversation_id,
                                langchain_id=current_message.tool_call_id
                            )
                            if tool_call_request_message is None:
                                continue
                            message_uuid = tool_call_request_message.id
                            tool_call_response_message = message_type_adapter.validate_json(tool_call_request_message.content)
                            
                            tool_call_response_message.additional_kwargs["hitl_status"]["status"] = "approved" # TODO
                            tool_call_response_message.content = current_message.content
                            await db_utils.db_update_message(
                                self.session_factory,
                                conversation_id=conversation_id,
                                message_id = message_uuid,
                                content = tool_call_response_message.model_dump_json(),
                                attachments = [],
                            )
                            deltas = self.parser.parse_message_delta(tool_call_response_message, message_uuid)
                        
                        log.debug("Received message chunk: %s", message_chunk)
                    elif event["type"] == "updates":
                        current_message = None
                        current_message_node = None
                        update_data = cast(dict[str, Any], event["data"])
                        chat_update = cast(dict[str, Any] | None, update_data.get(MAIN_MODEL_NODE_NAME))
                        if chat_update:
                            log.debug("Received chat update: %s", chat_update)
                            for msg in cast(list[AnyMessage], chat_update.get("messages", [])):
                                if not isinstance(msg, AIMessage):
                                    continue
                                await db_utils.db_update_message(
                                    self.session_factory,
                                    conversation_id=conversation_id,
                                    message_id = None,
                                    langchain_id = msg.id,
                                    content = msg.model_dump_json(),
                                    attachments = [],
                                )
                                
                                for tool_call in msg.tool_calls:
                                    tool_message = ToolMessage(
                                        content="",
                                        tool_call_id=tool_call['id'],
                                        name=tool_call['name'],
                                        additional_kwargs={
                                            "args": [
                                                {arg_name: arg_value}
                                                for arg_name, arg_value in tool_call['args'].items()
                                            ],
                                            "hitl_status": {
                                                "status":"approved",
                                                "pending_reason":"waiting for tool execution"
                                            }
                                        },
                                    )
                                    tool_message_id = await db_utils.db_update_message(
                                        self.session_factory,
                                        conversation_id=conversation_id,
                                        message_id = None,
                                        langchain_id = tool_call['id'],
                                        content = tool_message.model_dump_json(),
                                        attachments = [],
                                    )
                                    deltas.extend(self.parser.parse_message_delta(tool_message, tool_message_id))
                    elif event["type"] == "values":
                        value_event = cast(dict[str, Any], event)
                        interrupts = value_event.get("interrupts") or []
                        for interrupt in interrupts:
                            payload = interrupt.value
                            if not isinstance(payload, dict):
                                continue
                            if payload.get("type") == "user_input":
                                continue
                            tool_call_id = payload.get("tool_call_id")
                            if not tool_call_id:
                                continue
                            interrupt_message = payload.get("message", "")
                            tool_message_row = await db_utils.db_get_message_by_langchain_id(self.session_factory, conversation_id, tool_call_id)
                            if tool_message_row is None:
                                continue
                            tool_message = message_type_adapter.validate_json(tool_message_row.content)
                            if not isinstance(tool_message, ToolMessage):
                                continue
                            additional_kwargs = dict(tool_message.additional_kwargs)
                            additional_kwargs["hitl_status"] = {
                                "status": "pending",
                                "pending_reason": interrupt_message
                            }
                            tool_message.additional_kwargs = additional_kwargs
                            await db_utils.db_update_message(
                                self.session_factory,
                                conversation_id=conversation_id,
                                message_id = tool_message_row.id,
                                content = tool_message.model_dump_json(),
                                attachments = [],
                            )
                            deltas.extend(self.parser.parse_message_delta(tool_message, tool_message_row.id))

                    if deltas:
                        async with job.cond:
                            for delta in deltas:
                                job.history.append(delta)
                            job.cond.notify_all()
                
            except asyncio.CancelledError:
                if not job.delete_requested and current_message_node == MAIN_MODEL_NODE_NAME:
                    await _persist_partial_ai_message(current_message)
            except Exception as exc:
                if not is_langchain_network_failure(exc):
                    raise

                log.warning(
                    "Network failure while streaming conversation: conversation_id=%s, error=%s",
                    conversation_id,
                    exc,
                )
                if current_message_node == MAIN_MODEL_NODE_NAME:
                    await _persist_partial_ai_message(current_message)
                async with job.cond:
                    job.history.append(
                        CompletionResponseError(
                            error_message=str(exc) or "Network failure while streaming the model response."
                        )
                    )
                    job.cond.notify_all()
            finally:
                async with job.cond:
                    job.cond.notify_all()
                self._conversation_jobs.pop(conversation_id, None)
        
        job = self._conversation_jobs[conversation_id]
        job.run_task = None
        job.task = asyncio.create_task(_run(job))
        return job
        
    async def stream(self, conversation_id : str, need_history: bool, job: _ConversationJobState | None = None):
        if need_history:
            async def _get_history():
                async with self.session_factory() as session:
                    session : AsyncSession
                    messages_row = await session.execute(
                        select(db_models.Message).where(db_models.Message.conversation_id == conversation_id).order_by(db_models.Message.seq)
                    )
                    attachments_row = await session.execute(
                        select(db_models.MessageAttachment, db_models.Attachment)
                            .join(db_models.Attachment, db_models.Attachment.id == db_models.MessageAttachment.attachment_id)
                            .where(db_models.MessageAttachment.message_id.in_(
                                select(db_models.Message.id).
                                where(db_models.Message.conversation_id == conversation_id)))
                    )
                    attachment_map = {}
                    for msg_att, att in attachments_row:
                        if msg_att.message_id not in attachment_map:
                            attachment_map[msg_att.message_id] = []
                        attachment_map[msg_att.message_id].append(att.id)
                    return messages_row.scalars().all(), attachment_map
            history_messages, attachment_map = await asyncio.shield(_get_history())
        else:
            history_messages = []
            attachment_map = {}

        active_job = job or self._conversation_jobs.get(conversation_id)

        if active_job is not None:
            yield CompletionUserMessage(
                message_id = active_job.user_message_id,
            )
            
            idx = 0
            if need_history:
                finalized_messages = set()
                
                for message in history_messages:
                    yield CompletionResponseHistory(
                            message_id = message.id,
                            created_at = int(message.created_at.timestamp()),
                            finished_at = int(message.finished_at.timestamp()) if message.finished_at else int(message.created_at.timestamp()),
                            data = self.parser.parse_message(message_type_adapter.validate_json(message.content), attachment_map.get(message.id, []))
                        )
                    finalized_messages.add(message.id)
                
                log.debug(
                    "Last message seq in history: %s",
                    history_messages[-1].seq if history_messages else "No history messages",
                )
                while idx < len(active_job.history):
                    message_id = getattr(active_job.history[idx], "message_id", None)
                    if message_id is None or message_id not in finalized_messages:
                        break
                    idx += 1
                
            log.debug("Starting stream from idx %s", idx)
            while True:
                async with active_job.cond:
                    while idx < len(active_job.history):
                        yield active_job.history[idx]
                        idx += 1
                    if active_job.task and active_job.task.done() and idx >= len(active_job.history):
                        break
                    try:
                        await asyncio.wait_for(active_job.cond.wait(), timeout=2)
                    except asyncio.TimeoutError:
                        pass
        
        else:
            for message in history_messages:
                message_object = message_type_adapter.validate_json(message.content)
                yield CompletionResponseHistory(
                        message_id = message.id,
                        created_at = int(message.created_at.timestamp()),
                        finished_at = int(message.finished_at.timestamp()) if message.finished_at else int(message.created_at.timestamp()),
                        data = self.parser.parse_message(message_object, attachment_map.get(message.id, []))
                    )

    async def cancel(self, conversation_id : str):
        await self._stop_running_conversation(conversation_id)

    async def delete_conversation(self, conversation_id: str) -> bool:
        if conversation_id in self._conversation_jobs:
            self._conversation_jobs[conversation_id].delete_requested = True

        await self._stop_running_conversation(conversation_id)
        self.title_task_manager.cancel(conversation_id)
        return await delete_conversation_record(
            self.session_factory,
            self.graph,
            conversation_id,
        )

    async def _stop_running_conversation(self, conversation_id: str):
        job = self._conversation_jobs.get(conversation_id)
        if job is None:
            return

        current_task = asyncio.current_task()
        tasks_to_cancel = [
            task
            for task in (job.task, job.run_task)
            if task is not None and task is not current_task and not task.done()
        ]
        for task in tasks_to_cancel:
            task.cancel()

        for i in range(10*10):
            if conversation_id not in self._conversation_jobs:
                return
            await asyncio.sleep(0.1)
        raise ValueError(f"Failed to cancel conversation {conversation_id}")
