"""Message and thought-step schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ThoughtStep(BaseModel):
    id: str
    type: str
    content: str
    status: str
    create_at: int = Field(description="Epoch milliseconds")
    raw_json: str


class ChatMessage(BaseModel):
    message_id: str
    content: str
    role: Literal["system", "user", "assistant", "tool"]
    created_at: int
    thought_steps: list[ThoughtStep] = Field(default_factory=list)
