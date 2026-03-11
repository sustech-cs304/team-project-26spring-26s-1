"""Transform raw agent events into API-level stream events."""

from __future__ import annotations


class EventTransformer:
    """Maps runtime events into SSE payload dictionaries."""

    def to_sse_event(self, event: object) -> dict:
        raise NotImplementedError

    def to_db_payload(self, collected_events: list[dict]) -> dict:
        raise NotImplementedError
