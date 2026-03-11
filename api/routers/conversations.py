"""Conversation list/search endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.deps import get_conversation_service
from api.schemas.conversation import ConversationListOut
from api.services.conversation_service import ConversationService

router = APIRouter(tags=["conversations"])


@router.get("/conversations/", response_model=ConversationListOut)
async def list_conversations(
    page: Annotated[int, Query(ge=1)] = 1,
    pageSize: Annotated[int, Query(ge=10)] = 25,
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationListOut:
    result = await service.list(page=page, page_size=pageSize)
    return ConversationListOut.model_validate(result)


@router.get("/conversations/search", response_model=ConversationListOut)
async def search_conversations(
    keywords: str,
    page: Annotated[int, Query(ge=1)] = 1,
    pageSize: Annotated[int, Query(ge=10)] = 25,
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationListOut:
    result = await service.search(keywords=keywords, page=page, page_size=pageSize)
    return ConversationListOut.model_validate(result)
