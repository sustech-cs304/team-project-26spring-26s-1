import asyncio
from fastapi import APIRouter, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.responses import JSONResponse
import websockets
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import pydantic
from contextlib import suppress
from agent.db.models import Conversation
from agent.api.conversation_runner import ConversationRunner
from agent.api.conversation_service import (
    create_conversation as create_conversation_record,
    delete_conversation as delete_conversation_record,
    search_conversations as search_conversations_record,
)


router = APIRouter()


class ConversationCompletionRequest(pydantic.BaseModel):
    conversation_id: str
    request_id: str
    content: str | None = None
    created_at: int
    attachments: list[str] = []
    need_history: bool
    restart_message_id: str | None = None

@router.post("/conversation/completion", response_class=EventSourceResponse)
async def conversation_completion(params: ConversationCompletionRequest, request: Request):
    ConversationRunner = request.app.state.ConversationRunner
    run_task = asyncio.create_task(
        ConversationRunner.run(
            params.conversation_id,
            params.content or "",
            params.restart_message_id,
            params.attachments,
        )
    )
    await asyncio.shield(run_task)
    job = run_task.result()
    
    async for delta in ConversationRunner.stream(params.conversation_id, params.need_history, job):
        yield ServerSentEvent(
            data=delta,
            event=delta._event_type
        )
    yield ServerSentEvent(event="done")
    

class ConversationCreateResponse(pydantic.BaseModel):
    conversation_id: str
    created_at: int
    
@router.post("/conversation")
async def create_conversation(request: Request):
    conversation = await create_conversation_record(request.app.state.async_session)
    return ConversationCreateResponse(
        conversation_id=conversation.id,
        created_at=int(conversation.time_last_used.timestamp()),
    )


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


@router.get("/conversations/search", response_model=ConversationListResponse)
async def search_conversations(request: Request, keywords: str = "", page: int = 1, page_size: int = 25):
    session_factory = request.app.state.async_session
    runner: ConversationRunner = request.app.state.ConversationRunner

    if page < 1 or page_size < 1 or not keywords.strip():
        return JSONResponse(status_code=400, content={"message": "Invalid request parameters"})

    try:
        conversations = await search_conversations_record(session_factory, keywords, page, page_size)

        return ConversationListResponse(
            conversations=[
                ConversationListItem(
                    conversation_id=conv.id,
                    created_at=int(conv.time_last_used.timestamp()),
                    updated_at=int(conv.time_last_used.timestamp()),
                    title=conv.title,
                    is_active=runner.is_running(conv.id),
                    is_pinned=conv.pinned,
                )
                for conv in conversations
            ]
        )
    except Exception:
        return JSONResponse(status_code=500, content={"message": "Internal server error"})
        
@router.post("/conversation/cancelchat")
async def cancel_conversation(request: Request, conversation_id: str):
    runner : ConversationRunner = request.app.state.ConversationRunner
    
    if not runner.is_running(conversation_id):
        raise HTTPException(status_code=400, detail=f"Conversation {conversation_id} is not running")
    
    await runner.cancel(conversation_id)
    return {"status": "cancelled"}

@router.delete("/conversation/{conversation_id}")
async def delete_conversation(request: Request, conversation_id: str, restart_message_id: str | None = None):
    deleted = await delete_conversation_record(
        request.app.state.async_session,
        request.app.state.graph,
        conversation_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
        
@router.websocket("/conversation/asr")
async def conversation_asr(websocket: WebSocket):
    cfg = websocket.app.state.get_config()
    await websocket.accept()
 
    dashscope_ws = None
 
    try:
        dashscope_ws = await websockets.connect(
            cfg.api.asr.base_url,
            additional_headers={
                'Authorization': f'bearer {cfg.api.asr.api_key}',
            },
            max_size=None,
        )
        
        async def forward_client():
            while True:
                data = await websocket.receive()
                if data['type'] == 'websocket.disconnect':
                    break
                
                if 'text' in data:
                    await dashscope_ws.send(data['text'])
                elif 'bytes' in data:
                    await dashscope_ws.send(data['bytes'])
                
        async def forward_asr():
            while True:
                result = await dashscope_ws.recv()
                await websocket.send_text(result if isinstance(result, str) else result.decode('utf-8'))
                
        await asyncio.gather(forward_client(), forward_asr())

    except WebSocketDisconnect:
        pass
    except Exception as e:
        with suppress(Exception):
            await websocket.send_json({"error": str(e)})
        return
    finally:
        with suppress(Exception):
            if dashscope_ws:
                await dashscope_ws.close()
        with suppress(Exception):
            await websocket.close()
            
class ConversationUpdateRequest(pydantic.BaseModel):
    title: str | None = None
    is_pinned: bool | None = None
            
@router.patch("/conversation/{conversation_id}")
async def update_conversation_title(request: Request, conversation_id: str, params: ConversationUpdateRequest):
    session_factory = request.app.state.async_session
    
    async with session_factory() as session:
        session : AsyncSession
        
        stmt = update(Conversation).where(Conversation.id == conversation_id)
        
        if params.title is not None:
            stmt = stmt.values(title=params.title)
        if params.is_pinned is not None:
            stmt = stmt.values(pinned=params.is_pinned)
            
        result = await session.execute(stmt)
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
        await session.commit()

    return {"status": "updated"}
