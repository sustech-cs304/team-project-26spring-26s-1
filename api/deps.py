"""FastAPI dependency wiring for repositories and services."""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.repository import ConversationRepository
from api.db.session import get_async_session
from api.runtime.manager import ConversationRuntimeManager
from api.services.cancellation_service import CancellationService
from api.services.conversation_service import ConversationService
from api.services.history_service import HistoryService
from api.services.streaming_service import StreamingService


async def get_db_session(session: AsyncSession = Depends(get_async_session)) -> AsyncSession:
    return session


def get_runtime_manager(request: Request) -> ConversationRuntimeManager:
    return request.app.state.runtime_manager


def get_conversation_repo(session: AsyncSession = Depends(get_db_session)) -> ConversationRepository:
    return ConversationRepository(session=session)


def get_conversation_service(repo: ConversationRepository = Depends(get_conversation_repo)) -> ConversationService:
    return ConversationService(repo=repo)


def get_streaming_service(
    repo: ConversationRepository = Depends(get_conversation_repo),
    runtime_manager: ConversationRuntimeManager = Depends(get_runtime_manager),
) -> StreamingService:
    return StreamingService(repo=repo, runtime_manager=runtime_manager)


def get_cancellation_service(
    repo: ConversationRepository = Depends(get_conversation_repo),
    runtime_manager: ConversationRuntimeManager = Depends(get_runtime_manager),
) -> CancellationService:
    return CancellationService(repo=repo, runtime_manager=runtime_manager)


def get_history_service(repo: ConversationRepository = Depends(get_conversation_repo)) -> HistoryService:
    return HistoryService(repo=repo)
