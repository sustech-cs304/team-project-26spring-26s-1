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
from agent.parser.minimax import MinimaxEventParser
from uuid import uuid4
from fastapi.sse import ServerSentEvent
import datetime as dt
from langchain.messages import AnyMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from agent.api.utils import decode_message
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from bisect import bisect_right

class _ConversationJobState:
    def __init__(self):
        self.history = []
        self.history_message_seq = []
        self.cond = asyncio.Condition()
        self.done = False
        self.task : asyncio.Task = None # type: ignore
        self.user_message_id = None
        
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
            print("No user message provided, skipping graph execution and only loading history if needed")
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
                        print(f"Resuming conversation {conversation_id} from checkpoint {checkpoint_id}")
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
                    
                print(f"Message {message_id} saved to database with checkpoint {checkpoint_id} and seq {seq}")
        
        #give back and insert user message
        user_message_id = restart_message_id or str(uuid4())
        self._conversation_jobs[conversation_id].user_message_id = user_message_id
        await _db_update(conversation_id, user_message_id, HumanMessage(role = "user", content=user_message).model_dump_json(), checkpoint_id, self.seq)
        
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
                                job.history_message_seq.append(self.seq)
                                job.cond.notify_all()

                await _db_update(conversation_id, last_uuid, current_message.model_dump_json(), last_checkpoint, self.seq)
                self.seq += 1
                
            except asyncio.CancelledError:
                pass
            finally:
                async with job.cond:
                    job.done = True
                    job.cond.notify_all()
                self._conversation_jobs.pop(conversation_id, None)
        
        self._conversation_jobs[conversation_id].task = asyncio.create_task(_run(self._conversation_jobs[conversation_id]))
        
    async def stream(self, conversation_id : str, need_history: bool): # -> stream, add need_history
        if conversation_id in self._conversation_jobs:
            if need_history:
                async with self.session_factory() as session:
                    session : AsyncSession
                    messages_row = await session.execute(
                        select(db_models.Message).where(db_models.Message.conversation_id == conversation_id).order_by(db_models.Message.seq)
                    )
                messages = messages_row.scalars().all()
                h_messages : list[(CompletionResponseHistory, int)] = []
                for message in messages:
                    h_messages.append((
                        CompletionResponseHistory(
                            message_id = message.id,
                            created_at = int(message.created_at.timestamp()),
                            finished_at = int(message.finished_at.timestamp()) if message.finished_at else int(message.created_at.timestamp()),
                            data = decode_message(message)
                        ), message.seq)
                    )
            async def _stream(job: _ConversationJobState):
                #send user_message_id here
                if job.user_message_id:
                    yield CompletionUserMessage(message_id=job.user_message_id)
                    job.user_message_id = None
                
                idx = 0
                
                if need_history:
                    for h_message in h_messages:
                        yield h_message[0]
                    X = h_messages[-1][1] if h_messages else 0
                    idx = bisect_right(job.history_message_seq, X)
                    
                    print(f"Starting stream from idx {idx} with seq {X}")
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
            return _stream(self._conversation_jobs[conversation_id])
        else:
            async def _history_stream():
                if need_history:
                    async with self.session_factory() as session:
                        session : AsyncSession
                        messages_row = await session.execute(
                            select(db_models.Message).where(db_models.Message.conversation_id == conversation_id).order_by(db_models.Message.seq)
                        )
                        messages = messages_row.scalars().all()
                        h_messages : list[CompletionResponseHistory] = []
                        for message in messages:
                            h_messages.append(
                                CompletionResponseHistory(
                                    message_id = message.id,
                                    created_at = int(message.created_at.timestamp()),
                                    finished_at = int(message.finished_at.timestamp()) if message.finished_at else int(message.created_at.timestamp()),
                                    data = decode_message(message)
                                )
                            )
                    for h_message in h_messages:
                        yield h_message
            return _history_stream()

    def cancel(self, conversation_id : str):
        if conversation_id in self._conversation_jobs:
            job = self._conversation_jobs[conversation_id]
            if job.task:
                job.task.cancel()