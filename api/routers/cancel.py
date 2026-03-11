"""Conversation cancellation endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.deps import get_cancellation_service
from api.schemas.common import MessageResponse
from api.services.cancellation_service import CancellationService

router = APIRouter(tags=["cancel"])


@router.post("/conversation/cancelchat", response_model=MessageResponse)
async def cancel_chat(
    conversation_id: Annotated[str, Query()],
    message_id: Annotated[str, Query()],
    service: Annotated[CancellationService, Depends(get_cancellation_service)],
) -> MessageResponse:
    result = await service.cancel(conversation_id=conversation_id, message_id=message_id)
    return MessageResponse.model_validate(result)
