from typing import Literal, Annotated, Union, ClassVar
from unittest import runner
from fastapi import APIRouter, Request, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import pydantic
from agent.db.models import Conversation
import agent.api.models as api_models
import datetime as dt
from agent.api.conversation_runner import ConversationRunner
import langgraph.graph.state
from agent.core.state import AgentState
from langchain.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from agent.api.models import (
    CompletionResponseDelta,
    CompletionResponseHistory,
    CompletionResponseMetadata,
    CompletionResponseToolCall,
    CompletionResponseError,
    CompletionEventKeepAlive
)


router = APIRouter()

class ConversationCompletionRequest(pydantic.BaseModel):
    conversation_id: str
    request_id: str
    content: str | None = None
    created_at: int
    attachments: list[str] = []
    need_history: bool

@router.post("/conversation/completion", response_class=EventSourceResponse)
async def conversation_completion(params: ConversationCompletionRequest, request: Request):
    id = str(uuid4())
    
    ConversationRunner = request.app.state.ConversationRunner
    await ConversationRunner.run(params.conversation_id, params.content or "")
    
    async for event in ConversationRunner.listen(params.conversation_id):
        print(f"Yielding event: {event}")
        yield ServerSentEvent(
            data=CompletionResponseDelta(
                message_id=str(uuid4()),
                delta=str(event),
                is_thinking=False
            ),
            event=CompletionResponseDelta._event_type
        )
    yield ServerSentEvent(event='done')
    

class ConversationCreateResponse(pydantic.BaseModel):
    conversation_id: str
    created_at: int
    
@router.post("/conversation")
async def create_conversation(request: Request):
    session_factory = request.app.state.async_session
    
    id = str(uuid4())
    ts = dt.datetime.now(tz=dt.timezone.utc)
    conversation = Conversation(id=id, title=f"New Conversation", time_last_used=ts)
    
    async with session_factory() as session:
        session : AsyncSession
        
        session.add_all([conversation])
        await session.commit()
    return ConversationCreateResponse(conversation_id=id, created_at=int(ts.timestamp()))


class ConversationListItem(pydantic.BaseModel):
    conversation_id: str
    created_at: int
    updated_at: int
    title: str 
    is_active: bool
    is_pinned: bool

class ConversationListResponse(pydantic.BaseModel):
    conversations: list[ConversationListItem]

@router.get("/conversations/", response_model=ConversationListResponse)
async def list_conversations(request: Request, page: int = 1, page_size: int = 25):
    session_factory = request.app.state.async_session
    runner : ConversationRunner = request.app.state.ConversationRunner
    
    async with session_factory() as session:
        session : AsyncSession

        stmt = (
            select(Conversation)
            .order_by(Conversation.pinned.desc(), Conversation.time_last_used.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        
        result = await session.execute(stmt)
        conversations = result.scalars().all()
        
    return ConversationListResponse(
        conversations=[
            ConversationListItem(
                conversation_id=conv.id,
                created_at=int(conv.time_last_used.timestamp()),
                updated_at=int(conv.time_last_used.timestamp()),
                title=conv.title,
                is_active=runner.is_running(conv.id),
                is_pinned=conv.pinned
            )
            for conv in conversations
        ]
    )
        
@router.post("/conversation/cancelchat")
async def cancel_conversation(request: Request, conversation_id: str):
    runner : ConversationRunner = request.app.state.ConversationRunner
    
    if not runner.is_running(conversation_id):
        raise HTTPException(status_code=400, detail=f"Conversation {conversation_id} is not running")
    
    runner.cancel(conversation_id)
    return {"status": "cancelled"}
