import asyncio
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
    CompletionResponseDelta,
    CompletionResponseHistory,
    CompletionResponseMetadata,
    CompletionResponseToolCall,
    CompletionResponseError,
    CompletionEventKeepAlive
)

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
        pass
    
    def is_running(self, conversation_id: str) -> bool:
        return conversation_id in self._conversation_jobs
    
    async def run(self, conversation_id : str, user_message : str):
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
            
            checkpoint_message_row = await session.execute(
                select(db_models.Message).where(db_models.Message.conversation_id == conversation_id)
            )
            checkpoint_message = checkpoint_message_row.scalars().first()
            if checkpoint_message:
                checkpoint_id = checkpoint_message.checkpoint_id
                assert checkpoint_id is not None
        
        config = {
            "configurable": {
                "thread_id": conversation_id,
                "__utility_model": None,
                # "checkpoint_id": checkpoint_id
            }
        }
        # snapshot = await self.graph.aget_state(config)
        # result = self.graph.invoke(user_message,config)
        
        state = AgentState(
            messages=[HumanMessage(
                role="user",
                content=user_message or ""
            )],
        )

        gen =  self.graph.astream(state, config, version="v2",stream_mode=["messages","values","checkpoints"])
        
        
        async def _run(job: _ConversationJobState):
            try:
                async for message in gen:
                    async with job.cond:
                        job.history.append(message)
                        job.cond.notify_all()
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