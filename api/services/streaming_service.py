"""Streaming orchestration service."""

from __future__ import annotations

from collections.abc import AsyncIterator

from api.buffering.sse_encoder import encode_sse
from api.db.repository import ConversationRepository
from api.runtime.manager import ConversationRuntimeManager
from api.schemas.streaming import CompletionRequest


class StreamingService:
    """Coordinates request ingestion, worker lifecycle, and SSE output."""

    def __init__(
        self,
        repo: ConversationRepository,
        runtime_manager: ConversationRuntimeManager,
    ) -> None:
        self.repo = repo
        self.runtime_manager = runtime_manager

    async def stream_completion(
        self, payload: CompletionRequest
    ) -> AsyncIterator[bytes]:
        """Yield SSE-encoded bytes for one completion request."""
        # -- DB phase (commit before streaming) -------------------------
        conversation_id = payload.conversation_id
        if not conversation_id:
            conv = await self.repo.create_conversation()
            conversation_id = conv.conversation_id

        if payload.content:
            await self.repo.create_user_message(
                conversation_id=conversation_id,
                request_id=payload.request_id,
                content=payload.content,
            )

        # -- Streaming phase --------------------------------------------
        # subscribe_to_turn registers our queue *before* starting the
        # worker task, so no events can be lost.
        subscriber_queue, buffer = self.runtime_manager.subscribe_to_turn(
            conversation_id=conversation_id,
            user_input=payload.content or "",
        )

        # Send empty history as the first frame (populated later).
        yield encode_sse("history", {"messages": []})

        async for event in buffer.listen(subscriber_queue):
            yield encode_sse(
                event.get("event", "message_delta"), event.get("data", {})
            )
