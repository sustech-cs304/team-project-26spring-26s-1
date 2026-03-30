import asyncio
import json
from typing import Dict
import langgraph.graph.state
from agent.core.state import AgentState
from langchain.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
import agent.db.models as db_models
from sqlalchemy import select
import langgraph.graph.state
from agent.api.models import (
    ConversationMessage,
    ToolArgument,
    ToolMessage,
    HistoryMessage,
    CompletionResponseDelta,
    CompletionResponseHistory,
    CompletionResponseMetadata,
    CompletionResponseToolCall,
    CompletionResponseError,
    CompletionEventKeepAlive
)
from agent.parser.minimax import MinimaxEventParser
from uuid import uuid4
from fastapi.sse import ServerSentEvent
import datetime as dt

class _ConversationJobState:
    def __init__(self):
        self.history = []
        self.cond = asyncio.Condition()
        self.done = False
        self.task : asyncio.Task = None # type: ignore
        
class ConversationRunner:
    def __init__(self, graph : langgraph.graph.state.CompiledStateGraph, session_factory : async_sessionmaker):
        self._conversation_jobs: Dict[str, _ConversationJobState] = {}
        self.graph = graph
        self.session_factory = session_factory
        self.seq = 0
        pass
    
    def is_running(self, conversation_id: str) -> bool:
        return conversation_id in self._conversation_jobs
    
    async def run(self, conversation_id : str, user_message : str, need_history: bool):
        if conversation_id not in self._conversation_jobs:
            self._conversation_jobs[conversation_id] = _ConversationJobState()
        else:
            raise ValueError(f"Conversation {conversation_id} is already running")
        
        checkpoint_id = None
        
        async with self.session_factory() as session:
            session : AsyncSession
            
            conversation_row = await session.execute(
                select(db_models.Conversation).where(db_models.Conversation.id == conversation_id)
            )
            conversation = conversation_row.scalars().first()
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found in database")
            
            checkpoint_message_row = await session.execute(
                select(db_models.Message).where(db_models.Message.conversation_id == conversation_id)
                    .where(db_models.Message.checkpoint_id != None)
                    .order_by(db_models.Message.seq.desc()
                )
            )
            checkpoint_message = checkpoint_message_row.scalars().first()
            if checkpoint_message:
                checkpoint_id = checkpoint_message.checkpoint_id
                assert checkpoint_id is not None
                
            self.seq = conversation.message_seq + 1
        
        config : RunnableConfig = {
            "configurable": {
                "thread_id": conversation_id,
                "__utility_model": None,
                "checkpoint_id": checkpoint_id
            }
        }
        # snapshot = await self.graph.aget_state(config)
        # result = self.graph.invoke(user_message,config)
        
        state = AgentState(messages=([HumanMessage(role="user",content=user_message)]))
        
        def decode_message(message: db_models.Message) -> HistoryMessage:
            message_json = message.content
            
            def _extract_text(content: object) -> str:
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    chunks = []
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            chunks.append(str(item.get("text", "")))
                        else:
                            chunks.append(str(item))
                    return "".join(chunks)
                return str(content or "")

            def _split_thought(raw: str) -> tuple[str, str]:
                open_tag = "<think>"
                close_tag = "</think>"
                open_at = raw.find(open_tag)
                close_at = raw.find(close_tag)
                if open_at == -1 or close_at == -1 or close_at < open_at:
                    return "", raw
                thought = raw[open_at + len(open_tag):close_at].strip()
                content = (raw[:open_at] + raw[close_at + len(close_tag):]).strip()
                return thought, content

            payload = json.loads(message_json)
            message_type = str(payload.get("type", "")).lower()

            if "toolmessage" in message_type:
                raise NotImplementedError("ToolMessage parsing not implemented yet")

            role = "assistant"
            if "human" in message_type:
                role = "user"
            elif "system" in message_type:
                role = "system"

            raw_content = _extract_text(payload.get("content", ""))
            thought, content = _split_thought(raw_content)
            
            #TODO: attachments
            attachments = []
            for attachment in payload.get("attachments", []):
                if isinstance(attachment, dict) and "name" in attachment and "url" in attachment:
                    attachments.append(attachment["url"])
                elif isinstance(attachment, str):
                    attachments.append(attachment)

            return ConversationMessage(
                role=role,
                content=content,
                attachments=attachments,
                thought=thought,
            )

        async def _db_update(conversation_id: str, message_id: str, content: str, checkpoint_id: str, seq: int):
            now = dt.datetime.now(tz=dt.timezone.utc)
            
            async with self.session_factory() as session:
                session : AsyncSession
                async with session.begin():
                    conversation_row = await session.execute(
                        select(db_models.Conversation).where(db_models.Conversation.id == conversation_id)
                    )
                    conversation = conversation_row.scalar()
                    if not conversation:
                        raise ValueError(f"Conversation {conversation_id} not found in database during update")

                    message_row = db_models.Message(
                        id=message_id,
                        conversation_id=conversation_id,
                        content=content,
                        checkpoint_id=checkpoint_id,
                        seq=seq,
                        finished_at=now
                    )
                    session.add(message_row)
                    
                    conversation.message_seq = seq
                    conversation.time_last_used = now
                    # TODO: append message into conversation.messages
                    # conversation.messages.append(message_row)
                    
                print(f"Message {message_id} saved to database with checkpoint {checkpoint_id} and seq {seq}")


        print(f"Need history: {need_history}")
        if need_history:
            async with self.session_factory() as session:
                session : AsyncSession
                messages_row = await session.execute(
                    select(db_models.Message).where(db_models.Message.conversation_id == conversation_id).order_by(db_models.Message.seq)
                )
                messages = messages_row.scalars().all()
                async with self._conversation_jobs[conversation_id].cond:
                    for message in messages:
                        self._conversation_jobs[conversation_id].history.append(
                            CompletionResponseHistory(
                                message_id = message.id,
                                created_at = int(message.created_at.timestamp()),
                                finished_at = int(message.finished_at.timestamp()) if message.finished_at else int(message.created_at.timestamp()),
                                data = decode_message(message)
                            )
                        )
                    self._conversation_jobs[conversation_id].cond.notify_all()
                print(f"Loaded {len(messages)} messages from database for conversation {conversation_id}")
                                
        

        if not user_message or user_message == "":
            print("No user message provided, skipping graph execution and only loading history if needed")
            async with self._conversation_jobs[conversation_id].cond:
                self._conversation_jobs[conversation_id].done = True
                self._conversation_jobs[conversation_id].cond.notify_all()
            return
        else:
            #insert user message
            await _db_update(conversation_id, str(uuid4()), HumanMessage(role = "user", content=user_message).model_dump_json(), checkpoint_id, self.seq)
            gen =  self.graph.astream(state, config, version="v2",stream_mode=["messages","checkpoints"])
        
        async def _run(job: _ConversationJobState):
            parser = MinimaxEventParser()
            current_message = None
            last_message = None
            last_id = None
            last_uuid = None
            last_checkpoint = None
            
            try:
                async for event in gen:
                    print(f"Received event: {event}")
                    if event["type"] == "checkpoints":
                        last_checkpoint = event["data"]["config"]["configurable"]["checkpoint_id"]
                    elif event["type"] == "messages":
                        message_chunk = event["data"][0]
                        current_id = message_chunk.id
                        if current_id != last_id:
                            if last_id is not None:
                                await _db_update(conversation_id, last_uuid, last_message.model_dump_json(), last_checkpoint, self.seq)
                            last_message = current_message
                            current_message = None
                            last_id = current_id
                            last_uuid = str(uuid4())
                            self.seq += 1
                        current_message = message_chunk if current_message is None else current_message + message_chunk
                        print(f"Current message updated to: {current_message}")
                        parseds = parser.parse_event(event) if current_message else None
                        for parsed in parseds:
                            async with job.cond:
                                job.history.append(
                                    CompletionResponseDelta(
                                        message_id = last_uuid,
                                        delta = parsed.delta,
                                        is_thinking = parsed.is_thinking
                                    )
                                )
                                job.cond.notify_all()

                await _db_update(conversation_id, last_uuid, current_message.model_dump_json(), last_checkpoint, self.seq)
                
            except asyncio.CancelledError:
                pass
            finally:
                async with job.cond:
                    job.done = True
                    job.cond.notify_all()
                self._conversation_jobs.pop(conversation_id, None)
        
        self._conversation_jobs[conversation_id].task = asyncio.create_task(_run(self._conversation_jobs[conversation_id]))
        
    def listen(self, conversation_id : str):
        async def _listen(job: _ConversationJobState):
            idx = 0
            while True:
                async with job.cond:
                    while idx < len(job.history):
                        yield job.history[idx]
                        idx += 1
                    if job.done:
                        break
                    try:
                        await asyncio.wait_for(job.cond.wait(), timeout=2)
                    except asyncio.TimeoutError:
                        pass
        return _listen(self._conversation_jobs[conversation_id])
                    
    def cancel(self, conversation_id : str):
        if conversation_id in self._conversation_jobs:
            job = self._conversation_jobs[conversation_id]
            if job.task:
                job.task.cancel()