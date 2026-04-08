import asyncio
from bisect import bisect_right
from pathlib import Path
from typing import Dict
from uuid import uuid4

from langchain.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field, TypeAdapter
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import agent.db.models as db_models
import agent.db.utils as db_utils
from agent.api.conversation_models import (
    CompletionEventKeepAlive,
    CompletionResponseDelta,
    CompletionResponseError,
    CompletionResponseHistory,
    CompletionResponseMetadata,
    CompletionResponseToolCall,
    CompletionUserMessage,
    HistoryMessage,
    ToolArgument,
    ToolMessage,
)
from agent.config import AppConfig
from agent.core.context import AgentContext
from agent.core.state import AgentState
from agent.parser import AnthropicEventParser

message_type_adapter = TypeAdapter(AnyMessage)

class _ConversationJobState:
    def __init__(self):
        self.history = []
        self.history_seq = []
        self.cond = asyncio.Condition()
        self.task : asyncio.Task = None # type: ignore
        self.user_message_id = ""
        self.parser = AnthropicEventParser() # TODO: select parser based on model type
        
class ConversationRunner:
    def __init__(self, graph, session_factory : async_sessionmaker, config: AppConfig):
        self._conversation_jobs: Dict[str, _ConversationJobState] = {}
        self.graph = graph
        self.session_factory = session_factory
        self.config = config
    
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
                            .where(db_models.Message.seq >= restart_message.seq)
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
                    
        else:
            async with self.session_factory() as session:
                session : AsyncSession
                last_message = await session.execute(
                    select(db_models.Message)
                        .where(db_models.Message.conversation_id == conversation_id)
                        .order_by(db_models.Message.seq.desc())
                        .limit(1)
                )
                last_message = last_message.scalars().first()
        
        config : RunnableConfig = {
            "configurable": {
                "thread_id": conversation_id
            }
        }
        
        static_context : AgentContext = {
            "config": self.config
        }
        
        #dealing with attachments
        async def _get_attachment(attachment_id: str):
            async with self.session_factory() as session:
                session : AsyncSession
                attachment_row = await session.execute(
                    select(db_models.Attachment).where(db_models.Attachment.id == attachment_id)
                )
                attachment = attachment_row.scalars().first()
                if not attachment:
                    raise ValueError(f"Attachment not found in database: attachment_id={attachment_id}")
                return attachment
        async def _load_attachment(attachment_id: str) -> tuple[str, str]: # content, name
            attachment = await _get_attachment(attachment_id)
            if attachment.status != "completed":
                # TODO: handle unparsed attachment in SSE flow.
                raise NotImplementedError("TODO: handle unparsed attachment in SSE flow")
            type = Path(attachment.path).suffix.lower()
            name = Path(attachment.path).name
            read_path = Path(attachment.path) if type == ".txt" else Path(attachment.path).with_suffix(".md")
            if not read_path.exists():
                # TODO: handle unparsed attachment in SSE flow.
                raise NotImplementedError("TODO: handle unparsed attachment in SSE flow")
            content = await asyncio.to_thread(lambda: read_path.read_text(encoding="utf-8"))
            return content, name
        
        async def _link_message_attachment(message_id: str, attachment_id: str, name: str | None = None):
            async with self.session_factory() as session:
                session : AsyncSession
                async with session.begin():
                    attachment = (await session.execute(
                        select(db_models.Attachment).where(db_models.Attachment.id == attachment_id)
                    )).scalar_one_or_none()
                    if not attachment:
                        raise ValueError(f"Attachment not found in database during linking: attachment_id={attachment_id}")
                    existed = (
                        await session.execute(
                            select(db_models.MessageAttachment)
                                .where(db_models.MessageAttachment.message_id == message_id)
                                .where(db_models.MessageAttachment.attachment_id == attachment_id)
                                .limit(1)
                        )
                    ).scalar_one_or_none()
                    if existed:
                        return
                    display_name = name or Path(attachment.path).name
                    message_attachment_row = db_models.MessageAttachment(
                        message_id=message_id,
                        attachment_id=attachment_id,
                        name=display_name
                    )
                    session.add(message_attachment_row)
        async def _link_message_attachments(message_id: str, attachment_ids: list[str]):
            for attachment_id in attachment_ids:
                print(f"Linking attachment {attachment_id} to message {message_id}")
                await _link_message_attachment(message_id, attachment_id)

        
        #give back and insert user message
        user_message_id = restart_message_id or str(uuid4())
        self._conversation_jobs[conversation_id].user_message_id = user_message_id
        
        human_message =  HumanMessage(role="user",content=user_message)
        human_message_with_attachments_content = f"User Input:\n{human_message.content}\n\n"
        attachment_idx = 0
        for attachment_id in attachments:
            attachment_content, attachment_name = await _load_attachment(attachment_id)
            human_message_with_attachments_content += f"Attachment {attachment_idx + 1} [{attachment_name}]:\n{attachment_content}\n\n"
            attachment_idx += 1
        human_message_with_attachments = HumanMessage(role="user",content=human_message_with_attachments_content)
        gen = self.graph.astream(
            AgentState(messages=[human_message_with_attachments]),
            config,
            context=static_context,
            version="v2",
            stream_mode=["messages","checkpoints","updates"]
        )
                
        async def _run(job: _ConversationJobState):
            current_message = None
            last_checkpoint = ""
            
            async with self.session_factory() as session:
                session : AsyncSession
                
                conversation_history_messages_row = await session.execute(
                    select(db_models.Message).where(db_models.Message.conversation_id == conversation_id).order_by(db_models.Message.seq)
                )
                conversation_history_messages = conversation_history_messages_row.scalars().all()
                
                job.parser.decode_history([
                    message_type_adapter.validate_json(message.content) 
                    for message in conversation_history_messages
                ])
                        
            try:
                async for event in gen:
                    deltas = []
                    # print(f"Received event: {event}")
                    if event["type"] == "checkpoints":
                        if not last_checkpoint: # store initial checkpoint with user message, as it is the checkpoint right after adding user message                            
                            await db_utils.db_update_message(
                                self.session_factory,
                                conversation_id=conversation_id,
                                message_id = user_message_id,
                                langchain_id = None,
                                content = human_message.model_dump_json(), # do not store message with injected attachment content
                                attachments = attachments
                            )
                            
                            #store user_message and attachments after user_message is added to database
                            if attachments:
                                await _link_message_attachments(user_message_id, attachments)
                        last_checkpoint = event["data"]["config"]["configurable"]["checkpoint_id"]
                    elif event["type"] == "messages":
                        message_chunk = event["data"][0]
                        current_message = current_message + message_chunk if current_message else message_chunk
                        
                        message_uuid = await db_utils.db_update_message(
                            self.session_factory,
                            conversation_id=conversation_id,
                            message_id = None,
                            langchain_id = current_message.id,
                            content = current_message.model_dump_json(),
                            attachments = []
                        )
                        
                        print(f"Received message chunk: {message_chunk}")
                        deltas = job.parser.parse_event(event, message_uuid)
                    elif event["type"] == "updates":
                        current_message = None
                        if event["data"].get("chat"):
                            print(f"Received chat update: {event['data']['chat']}")
                            for msg in event["data"]["chat"]["messages"]:
                                await db_utils.db_update_message(
                                    self.session_factory,
                                    conversation_id=conversation_id,
                                    message_id = None,
                                    langchain_id = msg.id,
                                    content = msg.model_dump_json(),
                                    attachments = []
                                )
                                job.parser.decode_history([msg])
                                
                                # for tool_message in msg.tool_calls:                                    
                                #     await _db_update(conversation_id, db_models.Message(
                                #         id=await _db_get_id(conversation_id, tool_message['id']),
                                #         conversation_id=conversation_id,
                                #         content=ToolMessage(
                                #             content="",
                                #             tool_call_id=tool_message['id']
                                #         ).model_dump_json(),
                                #         checkpoint_id=None,
                                #         seq=seq
                                #     ))

                    if deltas:
                        seq = (await db_utils.db_get_message_by_langchain_id(self.session_factory, current_message.id)).seq
                        
                        async with job.cond:
                            for delta in deltas:
                                job.history.append(delta)
                                job.history_seq.append(seq)
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
            if need_history:
                for message in history_messages:
                    yield CompletionResponseHistory(
                            message_id = message.id,
                            created_at = int(message.created_at.timestamp()),
                            finished_at = int(message.finished_at.timestamp()) if message.finished_at else int(message.created_at.timestamp()),
                            data = job.parser.parse_message(message_type_adapter.validate_json(message.content), attachment_map.get(message.id, []))
                        )
                
                print(f"Last message seq in history: {history_messages[-1].seq if history_messages else 'No history messages'}")
                last_seq = history_messages[-1].seq if history_messages else -1
                idx = bisect_right(job.history_seq, last_seq)
            else:
                idx = 0
                
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
                parser.decode_history([message_object])

    def cancel(self, conversation_id : str):
        if conversation_id in self._conversation_jobs:
            job = self._conversation_jobs[conversation_id]
            if job.task:
                job.task.cancel()