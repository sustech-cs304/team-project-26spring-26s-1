"""Routes for conversation CRUD and streaming completion."""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Config
from ..loop import (
    AgentLoop,
    DoneEvent,
    ReasoningEvent,
    TextDeltaEvent,
    ToolCallStartEvent,
    ToolResultEvent,
)
from .database import get_db
from .db_models import ConversationRow, MessageRow
from .models import (
    Conversation as ConversationSchema,
    ConversationDetail,
    ConversationList,
    ConversationUpdate,
    ErrorResponse,
    Message as MessageSchema,
    MessageResponse,
    MessageRole,
    ThoughtStep,
)

router = APIRouter()

ROOT_PARENT = "__root__"
_agent_loop: Optional[AgentLoop] = None
_agent_loop_lock = asyncio.Lock()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _generate_title(loop: AgentLoop, user_content: str) -> str:
    """Call the utility model to generate a short conversation title."""
    def _fallback_title(text: str) -> str:
        # Fast deterministic fallback: extract first useful phrase.
        t = re.sub(r"\s+", " ", (text or "").strip())
        if not t:
            return "聊天记录"
        t = re.sub(r"^[\-\*#\d\.\)\(\s]+", "", t)
        t = re.sub(r"[`*_~]", "", t)
        first = re.split(r"[。！？!?\n\r,，；;：:]", t, maxsplit=1)[0].strip()
        if len(first) < 3:
            first = t[:24].strip()
        first = first[:18].strip(" .，,;；:：")
        return first if first else "聊天记录"

    try:
        resp = await asyncio.wait_for(
            loop.utility_client.chat.completions.create(
                model=loop.config.utility_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是一个对话标题生成器。"
                            "根据用户的第一条消息，生成一个简洁准确的对话标题，3-15个字。"
                            "直接输出标题文字，不要加引号、书名号或其他标点。"
                        ),
                    },
                    {"role": "user", "content": user_content},
                ],
                max_tokens=32,
                stream=False,
                # DashScope/Qwen non-streaming requires this flag.
                extra_body={"enable_thinking": False},
            ),
            timeout=3.0,
        )
        raw = (resp.choices[0].message.content or "").strip()
        title = raw.strip('"\'《》『』「」').strip()
        return title[:64] if title else _fallback_title(user_content)
    except Exception:
        return _fallback_title(user_content)


def _new_message_id() -> str:
    return str(uuid.uuid4())


async def _get_or_create_agent_loop() -> AgentLoop:
    global _agent_loop
    if _agent_loop is not None:
        return _agent_loop
    async with _agent_loop_lock:
        if _agent_loop is None:
            _agent_loop = await AgentLoop.create(config=Config.from_yaml())
    return _agent_loop


async def shutdown_agent_loop() -> None:
    global _agent_loop
    if _agent_loop is None:
        return
    try:
        await _agent_loop.shutdown()
    finally:
        _agent_loop = None


async def _history_payload(db: AsyncSession, conversation_id: str) -> ConversationDetail:
    conv = await db.get(ConversationRow, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    stmt = (
        select(MessageRow)
        .where(MessageRow.conversation_id == conversation_id)
        .order_by(MessageRow.seq.asc())
    )
    msg_rows = (await db.scalars(stmt)).all()

    messages: list[MessageSchema] = []
    for m in msg_rows:
        raw_steps = m.thought_steps if isinstance(m.thought_steps, list) else []
        steps = [ThoughtStep(**step) for step in raw_steps]
        messages.append(
            MessageSchema(
                message_id=m.message_id,
                content=m.content,
                parent=m.parent_id,
                role=MessageRole(m.role),
                created_at=str(m.created_at),
                thought_steps=steps,
            )
        )

    return ConversationDetail(
        conversation_id=conv.conversation_id,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        title=conv.title,
        is_active=conv.is_active,
        is_pinned=conv.is_pinned,
        messages=messages,
    )


def _history_event_data(detail: ConversationDetail) -> dict:
    payload = detail.model_dump()
    payload["history_messages"] = payload.pop("messages", [])
    return payload


async def _next_seq(db: AsyncSession, conversation_id: str) -> int:
    max_seq = await db.scalar(
        select(func.max(MessageRow.seq)).where(MessageRow.conversation_id == conversation_id)
    )
    return (max_seq or 0) + 1


def _rows_to_agent_context(rows: list[MessageRow]) -> list[dict]:
    # Keep only core conversational turns for model context.
    out: list[dict] = []
    for row in rows:
        if row.role in {"user", "assistant", "system"} and row.content:
            out.append({"role": row.role, "content": row.content})
    return out


@router.post(
    "/conversation",
    summary="发起聊天接口",
    response_model=ConversationSchema,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        404: {"model": ErrorResponse, "description": "资源不存在"},
    },
)
async def create_conversation(
    db: AsyncSession = Depends(get_db),
) -> ConversationSchema:
    now = _now_ms()
    conversation_id = str(uuid.uuid4())
    title = "新对话"
    conv = ConversationRow(
        conversation_id=conversation_id,
        created_at=now,
        updated_at=now,
        title=title,
        is_active=True,
        is_pinned=False,
        context={},
        metadata_json={},
    )
    db.add(conv)
    await db.commit()
    return ConversationSchema(
        conversation_id=conv.conversation_id,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        title=conv.title,
        is_active=conv.is_active,
        is_pinned=conv.is_pinned,
    )


@router.post(
    "/conversation/completion",
    summary="流式聊天接口",
    responses={
        200: {"description": "SSE stream", "content": {"text/event-stream": {}}},
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        404: {"model": ErrorResponse, "description": "资源不存在"},
        429: {"model": ErrorResponse, "description": "API 调用配额已耗尽"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
)
async def completion_stream(
    conversation_id: Optional[str] = Form(..., description="当前对话id，空时创建新会话"),
    request_id: str = Form(..., description="前端生成的request_id"),
    content: str = Form(default="", description="用户消息内容"),
    create_at: int = Form(..., description="消息创建时间(epoch ms)"),
    attachments: list[str] = Form(default=[], description="附件id列表"),
    need_history: bool = Form(default=False, description="是否先返回历史"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    _ = attachments
    cid = (conversation_id or "").strip()
    if not cid:
        now = _now_ms()
        cid = str(uuid.uuid4())
        conv = ConversationRow(
            conversation_id=cid,
            created_at=now,
            updated_at=now,
            title="新对话",
            is_active=True,
            is_pinned=False,
            context={},
            metadata_json={},
        )
        db.add(conv)
        await db.commit()
    else:
        conv = await db.get(ConversationRow, cid)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

    async def _event_stream() -> AsyncGenerator[str, None]:
        nonlocal conv
        if need_history:
            history = await _history_payload(db, cid)
            yield _sse("history", _history_event_data(history))

        if not content.strip():
            yield _sse("done", {"request_id": request_id, "reason": "empty_content"})
            return

        # Idempotency: same request_id should not create duplicate user turns.
        existing_req = await db.get(MessageRow, request_id)
        if existing_req is not None:
            if existing_req.conversation_id != cid:
                yield _sse("error", {"request_id": request_id, "message": "request_id belongs to another conversation"})
                return
            yield _sse(
                "done",
                {
                    "conversation_id": cid,
                    "request_id": request_id,
                    "message_id": existing_req.message_id,
                    "created_at": conv.created_at,
                    "updated_at": conv.updated_at,
                    "title": conv.title,
                    "is_active": conv.is_active,
                    "is_pinned": conv.is_pinned,
                    "reason": "duplicate_request",
                },
            )
            return

        # Handle chain uniqueness conflict (conversation_id,parent_id) under concurrent writes.
        inserted_user = False
        for _ in range(3):
            now = _now_ms()
            parent_id = conv.last_message_id or ROOT_PARENT
            user_seq = await _next_seq(db, cid)
            user_row = MessageRow(
                message_id=request_id,
                conversation_id=cid,
                parent_id=parent_id,
                seq=user_seq,
                role="user",
                content=content,
                status="final",
                created_at=create_at,
                updated_at=now,
                thought_steps=[],
                metadata_json={},
            )
            db.add(user_row)
            conv.updated_at = now
            conv.last_message_id = request_id
            conv.last_message_at = create_at
            try:
                await db.commit()
                inserted_user = True
                break
            except IntegrityError:
                await db.rollback()
                fresh_conv = await db.get(ConversationRow, cid)
                if fresh_conv is None:
                    yield _sse("error", {"request_id": request_id, "message": "Conversation not found"})
                    return
                conv = fresh_conv
                existing_req = await db.get(MessageRow, request_id)
                if existing_req is not None and existing_req.conversation_id == cid:
                    yield _sse(
                        "done",
                        {
                            "conversation_id": cid,
                            "request_id": request_id,
                            "message_id": existing_req.message_id,
                            "created_at": conv.created_at,
                            "updated_at": conv.updated_at,
                            "title": conv.title,
                            "is_active": conv.is_active,
                            "is_pinned": conv.is_pinned,
                            "reason": "duplicate_request",
                        },
                    )
                    return

        if not inserted_user:
            yield _sse("error", {"request_id": request_id, "message": "Concurrent write conflict, please retry"})
            return

        assistant_id = _new_message_id()
        assistant_seq = await _next_seq(db, cid)
        assistant_created = _now_ms()
        assistant_row = MessageRow(
            message_id=assistant_id,
            conversation_id=cid,
            parent_id=request_id,
            seq=assistant_seq,
            role="assistant",
            content="",
            status="streaming",
            created_at=assistant_created,
            updated_at=assistant_created,
            thought_steps=[],
            metadata_json={},
        )
        db.add(assistant_row)
        conv.updated_at = assistant_created
        conv.last_message_id = assistant_id
        conv.last_message_at = assistant_created
        thought_steps: list[dict] = []
        full_content = ""
        try:
            await db.commit()
            loop = await _get_or_create_agent_loop()
            rows_stmt = (
                select(MessageRow)
                .where(MessageRow.conversation_id == cid)
                .order_by(MessageRow.seq.asc())
            )
            rows = (await db.scalars(rows_stmt)).all()
            ctx = loop.new_context() + _rows_to_agent_context(rows[:-2])

            # Tracks the current streaming reasoning step so all chunks share one UUID.
            _reasoning_step: dict | None = None
            # FIFO queue of tool_call steps awaiting their paired tool_response.
            _pending_tool_steps: list[dict] = []

            async for event in loop.step(ctx, content):
                if isinstance(event, TextDeltaEvent):
                    full_content += event.delta
                    yield _sse(
                        "message_delta",
                        {"request_id": request_id, "message_id": assistant_id, "delta": event.delta},
                    )
                elif isinstance(event, ReasoningEvent):
                    if _reasoning_step is None:
                        _reasoning_step = {
                            "id": _new_message_id(),
                            "type": "thought_steps",
                            "content": event.delta,
                            "status": "running",
                            "create_at": str(_now_ms()),
                            "raw_json": "{}",
                        }
                        thought_steps.append(_reasoning_step)
                    else:
                        _reasoning_step["content"] += event.delta
                    yield _sse(
                        "thought_step",
                        {"request_id": request_id, "message_id": assistant_id, "step": dict(_reasoning_step)},
                    )
                elif isinstance(event, ToolCallStartEvent):
                    if _reasoning_step is not None:
                        _reasoning_step["status"] = "done"
                        yield _sse(
                            "thought_step",
                            {"request_id": request_id, "message_id": assistant_id, "step": dict(_reasoning_step)},
                        )
                        _reasoning_step = None
                    step = {
                        "id": _new_message_id(),
                        "type": "tool_call",
                        "content": f"{event.name}: {json.dumps(event.arguments, ensure_ascii=False)}",
                        "status": "running",
                        "create_at": str(_now_ms()),
                        "raw_json": json.dumps(event.arguments, ensure_ascii=False),
                    }
                    thought_steps.append(step)
                    _pending_tool_steps.append(step)
                    yield _sse(
                        "thought_step",
                        {"request_id": request_id, "message_id": assistant_id, "step": step},
                    )
                elif isinstance(event, ToolResultEvent):
                    if _pending_tool_steps:
                        pending = _pending_tool_steps.pop(0)
                        pending["status"] = "done"
                        yield _sse(
                            "thought_step",
                            {"request_id": request_id, "message_id": assistant_id, "step": dict(pending)},
                        )
                    step = {
                        "id": _new_message_id(),
                        "type": "tool_response",
                        "content": event.result,
                        "status": "done",
                        "create_at": str(_now_ms()),
                        "raw_json": json.dumps(
                            {"name": event.name, "arguments": event.arguments},
                            ensure_ascii=False,
                        ),
                    }
                    thought_steps.append(step)
                    yield _sse(
                        "thought_step",
                        {"request_id": request_id, "message_id": assistant_id, "step": step},
                    )
                elif isinstance(event, DoneEvent):
                    if _reasoning_step is not None:
                        _reasoning_step["status"] = "done"
                        yield _sse(
                            "thought_step",
                            {
                                "request_id": request_id,
                                "message_id": assistant_id,
                                "step": dict(_reasoning_step),
                            },
                        )
                        _reasoning_step = None
                    assistant_row.content = full_content or event.response
                    assistant_row.status = "final"
                    assistant_row.updated_at = _now_ms()
                    for step in thought_steps:
                        if step["status"] == "running":
                            step["status"] = "done"
                    assistant_row.thought_steps = thought_steps
                    conv.updated_at = assistant_row.updated_at
                    await db.commit()

                    # 主回复完成后立即发送 done
                    yield _sse(
                        "done",
                        {
                            "conversation_id": cid,
                            "request_id": request_id,
                            "message_id": assistant_id,
                            "created_at": conv.created_at,
                            "updated_at": conv.updated_at,
                            "title": conv.title,
                            "is_active": conv.is_active,
                            "is_pinned": conv.is_pinned,
                        },
                    )

                    # 必须再发送 set_title 后才关闭连接；若生成失败则回退到当前标题。
                    title_for_event = conv.title
                    if conv.title == "新对话":
                        try:
                            generated_title = await _generate_title(loop, content)
                            if generated_title:
                                title_for_event = generated_title
                                if generated_title != conv.title:
                                    conv.title = generated_title
                                    await db.commit()
                        except Exception:
                            title_for_event = conv.title

                    yield _sse("set_title", {"conversation_id": cid, "title": title_for_event})
                    break
        except Exception as exc:
            try:
                assistant_row.status = "error"
                assistant_row.updated_at = _now_ms()
                assistant_row.metadata_json = {"error": str(exc)}
                await db.commit()
            except Exception:
                await db.rollback()
            yield _sse("error", {"request_id": request_id, "message": str(exc)})

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


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
    pageSize: int = Query(default=25, ge=10, description="每页条目数"),
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
    page_size: int = Query(default=25, ge=10, description="每页条目数"),
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


@router.get(
    "/conversation/{conversation_id}/messages",
    summary="获取对话内容接口（已废弃）",
    response_model=ConversationDetail,
    deprecated=True,
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
    return await _history_payload(db, conversation_id)


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
    request: Request = ...,
    title: Optional[str] = Form(default=None, min_length=3, max_length=64),
    is_pinned: Optional[bool] = Form(default=None),
    is_active: Optional[bool] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    conv = await db.get(ConversationRow, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    payload: dict = {}
    content_type = (request.headers.get("content-type", "") if request else "").lower()
    if "application/json" in content_type and request is not None:
        try:
            raw_json = await request.json()
            if isinstance(raw_json, dict):
                payload = raw_json
        except Exception:
            payload = {}
    else:
        payload = {
            "title": title,
            "is_pinned": is_pinned,
            "is_active": is_active,
        }

    body = ConversationUpdate(**payload)
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    for key, value in updates.items():
        setattr(conv, key, value)
    conv.updated_at = _now_ms()

    await db.commit()
    return MessageResponse(message="success")


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
