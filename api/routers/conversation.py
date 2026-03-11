"""Conversation creation and mutation endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from api.deps import get_conversation_service
from api.schemas.common import MessageResponse
from api.schemas.conversation import ConversationOut, ConversationPatchForm
from api.services.conversation_service import ConversationService

router = APIRouter(tags=["conversation"])


@router.post("/conversation", response_model=ConversationOut)
async def create_conversation(
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationOut:
    result = await service.create()
    return ConversationOut.model_validate(result)


@router.patch("/conversation/{conversation_id}", response_model=MessageResponse)
async def patch_conversation(
    conversation_id: str,
    form: Annotated[ConversationPatchForm, Depends(ConversationPatchForm.as_form)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> MessageResponse:
    result = await service.patch(
        conversation_id=conversation_id,
        title=form.title,
        is_pinned=form.is_pinned,
    )
    return MessageResponse.model_validate(result)


@router.delete("/conversation/{conversation_id}", response_model=MessageResponse)
async def delete_conversation(
    conversation_id: str,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> MessageResponse:
    result = await service.delete(conversation_id=conversation_id)
    return MessageResponse.model_validate(result)
