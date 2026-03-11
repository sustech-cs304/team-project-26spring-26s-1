"""Streaming completion endpoint (SSE)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.deps import get_streaming_service
from api.schemas.streaming import CompletionRequest
from api.services.streaming_service import StreamingService

router = APIRouter(tags=["completion"])


@router.post("/conversation/completion")
async def completion(
    payload: Annotated[CompletionRequest, Depends(CompletionRequest.as_form)],
    service: Annotated[StreamingService, Depends(get_streaming_service)],
) -> StreamingResponse:
    stream = service.stream_completion(payload)
    return StreamingResponse(stream, media_type="text/event-stream")
