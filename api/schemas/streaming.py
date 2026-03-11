"""Streaming request and event schemas."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import Form
from pydantic import BaseModel, Field


class CompletionRequest(BaseModel):
    conversation_id: str | None
    request_id: str
    content: str | None = None
    create_at: int
    attachments: list[str] = Field(default_factory=list)
    need_history: bool = False

    @classmethod
    def as_form(
        cls,
        conversation_id: Annotated[str | None, Form()] = None,
        request_id: Annotated[str, Form()] = "",
        content: Annotated[str | None, Form()] = None,
        create_at: Annotated[int, Form()] = 0,
        attachments: Annotated[list[str] | None, Form()] = None,
        need_history: Annotated[bool, Form()] = False,
    ) -> "CompletionRequest":
        return cls(
            conversation_id=conversation_id,
            request_id=request_id,
            content=content,
            create_at=create_at,
            attachments=attachments or [],
            need_history=need_history,
        )


class SSEEnvelope(BaseModel):
    event: Literal["history", "set_title", "thought_step", "message_delta", "done", "error"]
    data: dict
