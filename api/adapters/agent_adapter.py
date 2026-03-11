"""Adapter between API runtime and existing /agent loop."""

from __future__ import annotations

from collections.abc import AsyncIterator


class AgentAdapter:
    """Wraps the existing agent loop with API-facing method signatures.

    Replace the body of ``stream_turn`` with a real ``AgentLoop.step()``
    integration when implementing business logic.
    """

    async def stream_turn(
        self, conversation_id: str, user_input: str
    ) -> AsyncIterator[dict]:
        """Yield SSE-shaped event dicts for one user turn (stub)."""
        yield {
            "event": "set_title",
            "data": {"conversation_id": conversation_id, "title": "新对话"},
        }
        yield {"event": "done", "data": {"conversation_id": conversation_id}}
