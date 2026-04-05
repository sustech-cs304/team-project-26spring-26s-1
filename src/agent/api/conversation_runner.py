import asyncio
from typing import Dict
import langgraph.graph.state
from agent.core.state import AgentState
from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
import agent.db.models as db_models
from sqlalchemy import select, text, delete
import aiosqlite
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
    CompletionEventKeepAlive,
    CompletionUserMessage
)
from agent.parser import AnthropicEventParser
from uuid import uuid4
import datetime as dt
from langchain.messages import AnyMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from bisect import bisect_right
from pydantic import BaseModel, Field, TypeAdapter

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
    def __init__(self, graph : langgraph.graph.state.CompiledStateGraph, session_factory : async_sessionmaker):
        self._conversation_jobs: Dict[str, _ConversationJobState] = {}
        self.graph = graph
        self.session_factory = session_factory
    
    def is_running(self, conversation_id: str) -> bool:
        return conversation_id in self._conversation_jobs
    
    async def run(self, conversation_id : str, user_message : str, restart_message_id: str | None = None): # remove need_history and related logic
        if not user_message:# TODO: complete here when adding attachments
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
                    
                    seq = restart_message.seq
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
            seq = last_message.seq + 1 if last_message else 1
        
        config : RunnableConfig = {
            "configurable": {
                "thread_id": conversation_id,
                "__utility_model": None,
                # "checkpoint_id": checkpoint_id
            }
        }
        
        
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
                    
                    conversation.time_last_used = now
                    
                # print(f"Message {message_id} saved to database with checkpoint {checkpoint_id} and seq {seq}")
        
        #give back and insert user message
        user_message_id = restart_message_id or str(uuid4())
        self._conversation_jobs[conversation_id].user_message_id = user_message_id
        
        human_message =  HumanMessage(role="user",content=user_message)
        gen =  self.graph.astream(AgentState(messages=[human_message]), config, version="v2",stream_mode=["messages","checkpoints","updates"])
        
        print(f"Starting conversation runner for conversation {conversation_id} with user message id {user_message_id} and initial seq {seq}")
        
        async def _run(job: _ConversationJobState):
            current_uuid = None
            nonlocal seq
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
            
            id_map: Dict[str, str] = {}
            
            try:
                async for event in gen:
                    deltas = []
                    # print(f"Received event: {event}")
                    if event["type"] == "checkpoints":
                        if not last_checkpoint: # store initial checkpoint with user message, as it is the checkpoint right after adding user message
                            await _db_update(conversation_id, user_message_id, human_message.model_dump_json(), event["data"]["config"]["configurable"]["checkpoint_id"], seq)
                            seq += 1
                        last_checkpoint = event["data"]["config"]["configurable"]["checkpoint_id"]
                    elif event["type"] == "messages":
                        message_chunk = event["data"][0]
                        if id_map.get(message_chunk.id):
                            current_uuid = id_map[message_chunk.id]
                        else:
                            current_uuid = str(uuid4())
                            id_map[message_chunk.id] = current_uuid
                        deltas = job.parser.parse_event(event, current_uuid)
                    elif event["type"] == "updates":
                        if event["data"].get("chat"):
                            print(f"Received chat update: {event['data']['chat']}")
                            for msg in event["data"]["chat"]["messages"]:
                                current_message_uuid = id_map.get("msg_id")
                                await _db_update(conversation_id, current_message_uuid, msg.model_dump_json(), last_checkpoint, seq)
                                seq += 1
                                job.parser.decode_history([msg])
                                
                    if deltas:
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
                    return messages_row.scalars().all()
            history_messages = await asyncio.shield(_get_history())
        else:
            history_messages = []
        
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
                            data = job.parser.parse_message(message_type_adapter.validate_json(message.content))
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
                        data = parser.parse_message(message_object)
                    )
                parser.decode_history([message_object])

    def cancel(self, conversation_id : str):
        if conversation_id in self._conversation_jobs:
            job = self._conversation_jobs[conversation_id]
            if job.task:
                job.task.cancel()