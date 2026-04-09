import asyncio
from pathlib import Path
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
    CompletionResponseHistory,
    CompletionUserMessage,
)
from agent.api.title_generator import ConversationTitleGenerator
from agent.config import AppConfig
from agent.file_utils.utils import (
    PendingMessageAttachmentRef,
    bind_pending_message_attachments,
    load_attachment_content,
)
from agent.parser import AnthropicEventParser

message_type_adapter = TypeAdapter(AnyMessage)
TITLE_GENERATION_TIMEOUT_SECONDS = 60

class _ConversationJobState:
    def __init__(self):
        self.history = []
        self.cond = asyncio.Condition()
        self.task : asyncio.Task = None # type: ignore
        self.user_message_id = ""
        self.parser = AnthropicEventParser() # TODO: select parser based on model type


class TitleTaskManager:
    def __init__(self, session_factory: async_sessionmaker, config: AppConfig):
        self.session_factory = session_factory
        self.title_generator = ConversationTitleGenerator(config)
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
            print(
                f"Conversation title generation timed out after "
                f"{TITLE_GENERATION_TIMEOUT_SECONDS}s: conversation_id={conversation_id}"
            )
        except Exception as exc:
            print(
                f"Failed to update conversation title: "
                f"conversation_id={conversation_id}, error={exc}"
            )
        finally:
            self._cleanup_task(conversation_id)
        
class ConversationRunner:
    def __init__(self, graph, session_factory : async_sessionmaker, config: AppConfig):
        self._conversation_jobs: Dict[str, _ConversationJobState] = {}
        self.graph = graph
        self.session_factory = session_factory
        self.config = config
        
        self.title_task_manager = TitleTaskManager(
            self.session_factory,
            self.config,
        )
    
    def is_running(self, conversation_id: str) -> bool:
        return conversation_id in self._conversation_jobs
    
    async def run(self, conversation_id : str, user_message : str, restart_message_id: str | None = None, attachments: list[str] = []): # remove need_history and related logic
        if not user_message and not attachments:
            # print("No user message provided, skipping graph execution and only loading history if needed")
            return
        
        if conversation_id not in self._conversation_jobs:
            self._conversation_jobs[conversation_id] = _ConversationJobState()
        else:
            raise ValueError(f"Conversation {conversation_id} is already running")
        
        async with self.session_factory() as session:
            session : AsyncSession
            conversation_row = await session.execute(
                select(db_models.Conversation).where(db_models.Conversation.id == conversation_id)
            )
            conversation = conversation_row.scalars().first()
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found in database")
        
        # checkpoint_id = None
        
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
                    
                    # erase messages after restart_message_seq(inclusive)
                    await session.execute(
                        delete(db_models.Message)
                            .where(db_models.Message.conversation_id == conversation_id)
                            .where(db_models.Message.seq > restart_message.seq)
                        # db can update now, so we don't delete restart_message itself to keep foreign key
                    )
                    
                    # erase checkpoints after restart_message_seq(inclusive)
                    conn = self.graph.checkpointer.conn
                    await conn.execute(
                        "DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_id >= ?",
                        (conversation_id, restart_message.checkpoint_id)
                    )
                    await conn.execute(
                        "DELETE FROM writes WHERE thread_id = ? AND checkpoint_id >= ?",
                        (conversation_id, restart_message.checkpoint_id)
                    )
        
        config : RunnableConfig = {
            "configurable": {
                "thread_id": conversation_id
            }
        }
        
        async def _ensure_thread_waiting_for_resume():
            needs_prime = True
            try:
                snapshot = await self.graph.aget_state(config)
                needs_prime = len(snapshot.next) == 0
            except Exception:
                needs_prime = True

            if needs_prime:
                await self.graph.ainvoke({}, config, version="v2")

        #give back and insert user message
        user_message_id = restart_message_id or str(uuid4())
        self._conversation_jobs[conversation_id].user_message_id = user_message_id
        bound_attachments: list[PendingMessageAttachmentRef] = []
        attachment_ids: list[str] = []

        await db_utils.db_update_message(
            self.session_factory,
            conversation_id=conversation_id,
            message_id=user_message_id,
            langchain_id=None,
            content=HumanMessage(role="user", content=user_message).model_dump_json(),
            attachments=[],
        )

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
        
        human_message =  HumanMessage(role="user",content=user_message)
        if bound_attachments:
            try:
                human_message_with_attachments_content = f"User Input:\n{human_message.content}\n\n"
                attachment_idx = 0
                for attachment in bound_attachments:
                    attachment_content, attachment_name = await load_attachment_content(self.session_factory, attachment.attachment_id)
                    display_name = attachment.name or attachment_name
                    human_message_with_attachments_content += f"Attachment {attachment_idx + 1} [{display_name}]:\n{attachment_content}\n\n"
                    attachment_idx += 1
                human_message_with_attachments = HumanMessage(role="user",content=human_message_with_attachments_content)
            except HTTPException as exc:
                raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        else:
            human_message_with_attachments = human_message
        
        await _ensure_thread_waiting_for_resume()

        await db_utils.db_update_message(
            self.session_factory,
            conversation_id=conversation_id,
            message_id=user_message_id,
            langchain_id=None,
            content=human_message.model_dump_json(),
            attachments=attachment_ids,
        )
        self.title_task_manager.request_title_generation(
            conversation_id,
            conversation.title,
            user_message,
        )

        gen = self.graph.astream(
            Command(resume=human_message_with_attachments.content),
            config,
            version="v2",
            stream_mode=["messages","checkpoints","updates", "values"]
        )
                
        async def _run(job: _ConversationJobState):
            current_message: AnyMessage | None = None
            last_checkpoint = ""
            user_message_checkpoint_written = False
                        
            try:
                async for event in gen:
                    event: StreamPart
                    deltas = []
                    # print(f"Received event: {event}")
                    if event["type"] == "checkpoints":
                        checkpoint_payload = cast(dict[str, Any], event["data"])
                        checkpoint_config = cast(dict[str, Any], checkpoint_payload.get("config", {}))
                        checkpoint_runtime = cast(dict[str, Any], checkpoint_config.get("configurable", {}))
                        checkpoint = checkpoint_runtime.get("checkpoint_id")
                        if checkpoint:
                            last_checkpoint = checkpoint
                        if checkpoint and not user_message_checkpoint_written:
                            await db_utils.db_update_message(
                                self.session_factory,
                                conversation_id=conversation_id,
                                message_id = user_message_id,
                                langchain_id = None,
                                content = human_message.model_dump_json(), # do not store message with injected attachment content
                                attachments = attachment_ids,
                                checkpoint_id = checkpoint
                            )
                            user_message_checkpoint_written = True
                    elif event["type"] == "messages":
                        message_data = cast(tuple[AnyMessage, dict[str, Any]], event["data"])
                        message_chunk, message_meta = message_data
                        current_message = current_message + message_chunk if current_message else message_chunk
                        
                        if isinstance(current_message, HumanMessage):
                            continue # we do not wish to store the message with injected attachment content
                        
                        if isinstance(current_message, AIMessage):
                            message_uuid = await db_utils.db_update_message(
                                self.session_factory,
                                conversation_id=conversation_id,
                                message_id = None,
                                langchain_id = current_message.id,
                                content = current_message.model_dump_json(),
                                attachments = []
                            )
                            deltas = job.parser.parse_event(event, message_uuid)
                        
                        if isinstance(current_message, ToolMessage):
                            tool_call_request_message = await db_utils.db_get_message_by_langchain_id(
                                self.session_factory,
                                conversation_id=conversation_id,
                                langchain_id=current_message.tool_call_id
                            )
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
                                checkpoint_id = last_checkpoint
                            )
                            deltas = job.parser.parse_message_delta(tool_call_response_message, message_uuid)
                        
                        print(f"Received message chunk: {message_chunk}")
                    elif event["type"] == "updates":
                        current_message = None
                        update_data = cast(dict[str, Any], event["data"])
                        chat_update = cast(dict[str, Any] | None, update_data.get("chat"))
                        if chat_update:
                            print(f"Received chat update: {chat_update}")
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
                                    checkpoint_id = last_checkpoint
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
                                        checkpoint_id = last_checkpoint
                                    )
                                    deltas.extend(job.parser.parse_message_delta(tool_message, tool_message_id))
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
                                checkpoint_id = last_checkpoint
                            )
                            deltas.extend(job.parser.parse_message_delta(tool_message, tool_message_row.id))

                    if deltas:
                        async with job.cond:
                            for delta in deltas:
                                job.history.append(delta)
                            job.cond.notify_all()
                
            except asyncio.CancelledError:
                pass
            finally:
                async with job.cond:
                    job.cond.notify_all()
                self._conversation_jobs.pop(conversation_id, None)
        
        self._conversation_jobs[conversation_id].task = asyncio.create_task(_run(self._conversation_jobs[conversation_id]))
        
    async def stream(self, conversation_id : str, need_history: bool):
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

        if conversation_id in self._conversation_jobs:
            yield CompletionUserMessage(
                message_id = self._conversation_jobs[conversation_id].user_message_id,
            )
            
            job = self._conversation_jobs[conversation_id]
            idx = 0
            if need_history:
                finalized_messages = set()
                
                for message in history_messages:
                    yield CompletionResponseHistory(
                            message_id = message.id,
                            created_at = int(message.created_at.timestamp()),
                            finished_at = int(message.finished_at.timestamp()) if message.finished_at else int(message.created_at.timestamp()),
                            data = job.parser.parse_message(message_type_adapter.validate_json(message.content), attachment_map.get(message.id, []))
                        )
                    finalized_messages.add(message.id)
                
                print(f"Last message seq in history: {history_messages[-1].seq if history_messages else 'No history messages'}")
                while idx < len(job.history) and job.history[idx].message_id in finalized_messages:
                    idx += 1
                
            print(f"Starting stream from idx {idx}")
            while True:
                async with job.cond:
                    while idx < len(job.history):
                        yield job.history[idx]
                        idx += 1
                    if self._conversation_jobs.get(conversation_id) != job:
                        break
                    try:
                        await asyncio.wait_for(job.cond.wait(), timeout=2)
                    except asyncio.TimeoutError:
                        pass
        
        else:
            parser = AnthropicEventParser()
            for message in history_messages:
                message_object = message_type_adapter.validate_json(message.content)
                yield CompletionResponseHistory(
                        message_id = message.id,
                        created_at = int(message.created_at.timestamp()),
                        finished_at = int(message.finished_at.timestamp()) if message.finished_at else int(message.created_at.timestamp()),
                        data = parser.parse_message(message_object, attachment_map.get(message.id, []))
                    )

    async def cancel(self, conversation_id : str):
        if conversation_id in self._conversation_jobs:
            job = self._conversation_jobs[conversation_id]
            if job.task:
                job.task.cancel()
            
            for i in range(10*10):
                if conversation_id not in self._conversation_jobs:
                    return
                await asyncio.sleep(0.1)
            raise ValueError(f"Failed to cancel conversation {conversation_id}")
        
<<<<<<< HEAD
                
=======
                
>>>>>>> 9f25f03... backend - fix cancel returning before the task is torn down.
