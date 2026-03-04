"""Pydantic models for the API, derived from the OpenAPI specification."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────


class MessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tools = "tools"


# ── Core domain models ──────────────────────────────────────────────────────


class ThoughtStep(BaseModel):
    """A single reasoning / tool-use step emitted by the assistant."""

    id: str
    type: str = Field(..., description="Step type – used by the frontend to render an icon")
    content: str
    status: str = Field(..., description="Step status")
    create_at: str = Field(..., description="Creation timestamp")
    raw_json: str = Field(..., description="Auxiliary information")


class Message(BaseModel):
    """A single message inside a conversation."""

    message_id: str
    content: str
    parent: str = Field(..., description="Parent message id")
    role: MessageRole
    created_at: str
    thought_steps: list[ThoughtStep] = Field(default_factory=list)


class Conversation(BaseModel):
    """Conversation summary (used in listing endpoints)."""

    conversation_id: str
    created_at: int
    updated_at: int
    title: str
    is_active: bool
    is_pinned: bool


class ConversationDetail(Conversation):
    """Full conversation including its messages."""

    messages: list[Message] = Field(default_factory=list)


# ── Request models ──────────────────────────────────────────────────────────


class ConversationRequest(BaseModel):
    """Body of ``POST /conversation`` (streaming chat)."""

    conversation_id: str
    message_id: str
    content: str
    parent_message_id: str
    create_at: str
    attachments: list[str] = Field(default_factory=list)


class ConversationUpdate(BaseModel):
    """Body of ``PATCH /conversation/{conversation_id}``.

    All fields are optional – only the supplied keys will be applied.
    """

    title: Optional[str] = Field(default=None, description="新会话标题")
    is_pinned: Optional[bool] = Field(default=None, description="true为置顶聊天，false为取消置顶")
    is_active: Optional[bool] = Field(default=None, description="会话是否进行中")


# ── Response models ─────────────────────────────────────────────────────────


class ConversationList(BaseModel):
    """Response for conversation listing / search endpoints."""

    conversations: list[Conversation] = Field(default_factory=list)


class MessageResponse(BaseModel):
    """Generic { "message": "..." } envelope."""

    message: str


class IcebreakerTopic(BaseModel):
    """A single recommended topic."""

    topic: str
    prompt: str


class IcebreakerResponse(BaseModel):
    """Response for ``GET /chat/icebreakers``."""

    topics: list[IcebreakerTopic] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Standard error body (400 / 404 / 429 / 500)."""

    message: str
