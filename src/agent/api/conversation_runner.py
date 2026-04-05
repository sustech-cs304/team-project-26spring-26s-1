import asyncio
from typing import Dict
import langgraph.graph.state
from agent.core.state import AgentState
from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
import agent.db.models as db_models
from sqlalchemy import select, text
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
        self.history_message_seq = []
        self.cond = asyncio.Condition()
        self.done = False
        self.task : asyncio.Task = None # type: ignore
        self.user_message_id = None
        self.parser = AnthropicEventParser() # TODO: select parser based on model type
        
class ConversationRunner:
    def __init__(self, graph : langgraph.graph.state.CompiledStateGraph, session_factory : async_sessionmaker):
        self._conversation_jobs: Dict[str, _ConversationJobState] = {}
        self.graph = graph
        self.session_factory = session_factory
        self.seq = 0
    
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
        
        checkpoint_id = None
        
        async with self.session_factory() as session:
            session : AsyncSession
            async with session.begin():
                conversation_row = await session.execute(
                    select(db_models.Conversation).where(db_models.Conversation.id == conversation_id)
                )
                conversation = conversation_row.scalars().first()
                if not conversation:
                    raise ValueError(f"Conversation {conversation_id} not found in database")
                
                if restart_message_id:
                    restart_message_row = await session.execute(
                        select(db_models.Message).where(db_models.Message.conversation_id == conversation_id)
                            .where(db_models.Message.id == restart_message_id)
                    )
                    restart_message = restart_message_row.scalars().first()
                    if restart_message:
                        checkpoint_message_row = await session.execute(
                            select(db_models.Message).where(db_models.Message.conversation_id == conversation_id)
                                .where(db_models.Message.seq < restart_message.seq)
                                .where(db_models.Message.checkpoint_id.is_not(None))
                                .order_by(db_models.Message.seq.desc())
                        )
                        checkpoint_message = checkpoint_message_row.scalars().first()
                        if checkpoint_message:
                            checkpoint_id = checkpoint_message.checkpoint_id
                            assert checkpoint_id is not None, "Checkpoint message must have a checkpoint_id"
                        
                        self.seq = checkpoint_message.seq + 1 if checkpoint_message else 1
                        
                        #delete messages after restart_message
                        await session.execute(
                            db_models.Message.__table__.delete().where(db_models.Message.conversation_id == conversation_id)
                                .where(db_models.Message.seq >= restart_message.seq)
                        )
                        
                        #TODO: delete attachments that are no longer referenced by any messages after deleting messages
                    else:
                        raise ValueError(f"Restart message {restart_message_id} not found in conversation {conversation_id}")
                else:
                    checkpoint_message_row = await session.execute(
                        select(db_models.Message).where(db_models.Message.conversation_id == conversation_id)
                            .where(db_models.Message.checkpoint_id.is_not(None))
                            .order_by(db_models.Message.seq.desc())
                    )
                    checkpoint_message = checkpoint_message_row.scalars().first()
                    if checkpoint_message:
                        checkpoint_id = checkpoint_message.checkpoint_id
                        assert checkpoint_id is not None
                        # print(f"Resuming conversation {conversation_id} from checkpoint {checkpoint_id}")
                    self.seq = checkpoint_message.seq + 1 if checkpoint_message else 1
        
        #delete checkpoints after deleting messages, here we cannot use ORM
        if restart_message_id:
            conn = self.graph.checkpointer.conn
            if checkpoint_id:
                stmt_checkpoints = "DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_id > ?"
                stmt_writes = "DELETE FROM writes WHERE thread_id = ? AND checkpoint_id > ?"
                params = (conversation_id, checkpoint_id)
                await conn.execute(stmt_checkpoints, params)
                await conn.execute(stmt_writes, params)
                await conn.commit()
            else:
                await self.graph.checkpointer.adelete_thread(conversation_id)
        
        config : RunnableConfig = {
            "configurable": {
                "thread_id": conversation_id,
                "__utility_model": None,
                "checkpoint_id": checkpoint_id
            }
        }
        
        state = AgentState(messages=([HumanMessage(role="user",content=user_message)]))
        
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
        await _db_update(conversation_id, user_message_id, HumanMessage(role = "user", content=user_message).model_dump_json(), checkpoint_id, self.seq)
        
        gen =  self.graph.astream(state, config, version="v2",stream_mode=["messages","checkpoints","updates"])
        
        async def _run(job: _ConversationJobState):
            current_uuid = None
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
                                current_message_uuid = msg.id
                                await _db_update(conversation_id, current_message_uuid, msg.model_dump_json(), last_checkpoint, self.seq)
                                job.parser.decode_history([msg])
                                
                    if deltas:
                        async with job.cond:
                            for delta in deltas:
                                job.history.append(delta)
                                job.history_message_seq.append(self.seq)
                            job.cond.notify_all()
                self.seq += 1
                
            except asyncio.CancelledError:
                pass
            finally:
                async with job.cond:
                    job.done = True
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
            job = self._conversation_jobs[conversation_id]
            if need_history:
                for message in history_messages:
                    yield CompletionResponseHistory(
                            message_id = message.id,
                            created_at = int(message.created_at.timestamp()),
                            finished_at = int(message.finished_at.timestamp()) if message.finished_at else int(message.created_at.timestamp()),
                            data = job.parser.parse_message(message_type_adapter.validate_json(message.content))
                        )
                
                last_seq = history_messages[-1].seq if history_messages else -1
                idx = bisect_right(job.history_message_seq, last_seq)
            else:
                idx = 0
                
            print(f"Starting stream from idx {idx}")
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