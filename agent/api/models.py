"""Pydantic models for the API."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class ThoughtStep(BaseModel):
    id: str
    type: str = Field(..., description="Step type, used by frontend icon rendering")
    content: str
    status: str = Field(..., description="Step status")
    create_at: str = Field(..., description="Epoch milliseconds as string")
    raw_json: str = Field(..., description="Extra payload as JSON string")


class Message(BaseModel):
    message_id: str
    content: str
    parent: str
    role: MessageRole
    created_at: str
    thought_steps: list[ThoughtStep] = Field(default_factory=list)


class Conversation(BaseModel):
    conversation_id: str
    created_at: int
    updated_at: int
    title: str
    is_active: bool
    is_pinned: bool


class ConversationDetail(Conversation):
    messages: list[Message] = Field(default_factory=list)


class ConversationCompletionRequest(BaseModel):
    conversation_id: str
    request_id: str
    content: str = ""
    create_at: int
    attachments: list[str] = Field(default_factory=list)
    need_history: bool = False


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=64)
    is_pinned: Optional[bool] = None


class ConversationList(BaseModel):
    conversations: list[Conversation] = Field(default_factory=list)


class MessageResponse(BaseModel):
    message: str


class IcebreakerTopic(BaseModel):
    topic: str
    prompt: str


class IcebreakerResponse(BaseModel):
    topics: list[IcebreakerTopic] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    message: str
