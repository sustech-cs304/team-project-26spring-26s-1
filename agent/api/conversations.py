"""Routes for conversation CRUD and streaming chat."""

from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Query, UploadFile, File, Path
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .db_models import ConversationRow, MessageRow
from .models import (
    Conversation as ConversationSchema,
    ConversationDetail,
    ConversationList,
    ConversationRequest,
    ConversationUpdate,
    ErrorResponse,
    Message as MessageSchema,
    MessageResponse,
    MessageRole,
    ThoughtStep,
)

router = APIRouter()


# ── POST /conversation  –  streaming chat ────────────────────────────────────


@router.post(
    "/conversation",
    summary="流式聊天接口",
    responses={
        200: {"description": "SSE stream", "content": {"text/event-stream": {}}},
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        429: {"model": ErrorResponse, "description": "API 调用配额已耗尽"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
)
async def stream_chat(
    conversation_id: str = Form(..., description="当前对话id"),
    message_id: str = Form(..., description="前端生成的message_id"),
    content: str = Form(..., description="用户消息内容"),
    parent_message_id: str = Form(..., description="父消息节点id"),
    create_at: str = Form(..., description="消息创建时间"),
    attachments: list[str] = Form(default=[], description="附件id列表"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    now = int(time.time())

    # Ensure conversation row exists (create on first message)
    conv = await db.get(ConversationRow, conversation_id)
    if conv is None:
        conv = ConversationRow(
            conversation_id=conversation_id,
            created_at=now,
            updated_at=now,
            is_active=True,
        )
        db.add(conv)
    else:
        conv.updated_at = now

    # Persist the user message
    msg = MessageRow(
        message_id=message_id,
        conversation_id=conversation_id,
        content=content,
        parent=parent_message_id if parent_message_id else None,
        role="user",
        created_at=now,
    )
    db.add(msg)
    await db.commit()

    # TODO: wire up agent pipeline and return an SSE stream
    async def _placeholder():
        yield "data: {}\n\n"

    return StreamingResponse(_placeholder(), media_type="text/event-stream")


# ── GET /conversations/  –  list conversations ──────────────────────────────


@router.get(
    "/conversations/",
    summary="获取历史对话列表接口",
    response_model=ConversationList,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
)
async def list_conversations(
    page: int = Query(default=1, ge=1, description="页码"),
    pageSize: int = Query(default=25, ge=10, description="每一页显示多少条消息"),
    db: AsyncSession = Depends(get_db),
) -> ConversationList:
    offset = (page - 1) * pageSize
    stmt = (
        select(ConversationRow)
        .order_by(ConversationRow.is_pinned.desc(), ConversationRow.updated_at.desc())
        .offset(offset)
        .limit(pageSize)
    )
    rows = (await db.scalars(stmt)).all()
    return ConversationList(
        conversations=[
            ConversationSchema(
                conversation_id=r.conversation_id,
                created_at=r.created_at,
                updated_at=r.updated_at,
                title=r.title,
                is_active=r.is_active,
                is_pinned=r.is_pinned,
            )
            for r in rows
        ]
    )


# ── GET /conversations/search  –  search conversations ──────────────────────


@router.get(
    "/conversations/search",
    summary="历史对话搜索接口",
    response_model=ConversationList,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
)
async def search_conversations(
    keywords: str = Query(..., description="搜索关键词"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=25, ge=10, description="每一页显示多少条消息"),
    db: AsyncSession = Depends(get_db),
) -> ConversationList:
    offset = (page - 1) * page_size
    pattern = f"%{keywords}%"
    stmt = (
        select(ConversationRow)
        .where(ConversationRow.title.ilike(pattern))
        .order_by(ConversationRow.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.scalars(stmt)).all()
    return ConversationList(
        conversations=[
            ConversationSchema(
                conversation_id=r.conversation_id,
                created_at=r.created_at,
                updated_at=r.updated_at,
                title=r.title,
                is_active=r.is_active,
                is_pinned=r.is_pinned,
            )
            for r in rows
        ]
    )


# ── GET /conversation/{conversation_id}/messages  –  get messages ────────────


@router.get(
    "/conversation/{conversation_id}/messages",
    summary="获取对话内容接口",
    response_model=ConversationDetail,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        404: {"model": ErrorResponse, "description": "资源不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
)
async def get_conversation_messages(
    conversation_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    conv = await db.get(ConversationRow, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    stmt = (
        select(MessageRow)
        .where(MessageRow.conversation_id == conversation_id)
        .order_by(MessageRow.created_at)
    )
    msg_rows = (await db.scalars(stmt)).all()

    return ConversationDetail(
        conversation_id=conv.conversation_id,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        title=conv.title,
        is_active=conv.is_active,
        is_pinned=conv.is_pinned,
        messages=[
            MessageSchema(
                message_id=m.message_id,
                content=m.content,
                parent=m.parent or "",
                role=MessageRole(m.role),
                created_at=str(m.created_at),
                thought_steps=[
                    ThoughtStep(**s) for s in (m.thought_steps if isinstance(m.thought_steps, list) else [])
                ],
            )
            for m in msg_rows
        ],
    )


# ── PATCH /conversation/{conversation_id}  –  update conversation ────────────


@router.patch(
    "/conversation/{conversation_id}",
    summary="更新对话接口",
    response_model=MessageResponse,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        404: {"model": ErrorResponse, "description": "资源不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
)
async def update_conversation(
    conversation_id: str = Path(...),
    body: ConversationUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    conv = await db.get(ConversationRow, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    for key, value in updates.items():
        setattr(conv, key, value)
    conv.updated_at = int(time.time())

    await db.commit()
    return MessageResponse(message="success")


# ── DELETE /conversation/{conversation_id}  –  delete ────────────────────────


@router.delete(
    "/conversation/{conversation_id}",
    summary="删除对话接口",
    response_model=MessageResponse,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        404: {"model": ErrorResponse, "description": "资源不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
)
async def delete_conversation(
    conversation_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    conv = await db.get(ConversationRow, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.delete(conv)
    await db.commit()
    return MessageResponse(message="success")
