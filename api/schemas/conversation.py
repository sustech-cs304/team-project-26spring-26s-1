"""Conversation request/response schemas."""

from __future__ import annotations

from typing import Annotated

from fastapi import Form
from pydantic import BaseModel, Field

from .message import ChatMessage


class ConversationOut(BaseModel):
    conversation_id: str
    created_at: int
    updated_at: int
    title: str = "新对话"
    is_active: bool
    is_pinned: bool


class ConversationListOut(BaseModel):
    conversations: list[ConversationOut] = Field(default_factory=list)


class ConversationPatchForm(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=64)
    is_pinned: bool | None = None

    @classmethod
    def as_form(
        cls,
        title: Annotated[str | None, Form()] = None,
        is_pinned: Annotated[bool | None, Form()] = None,
    ) -> "ConversationPatchForm":
        return cls(title=title, is_pinned=is_pinned)


class HistoryPayload(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
