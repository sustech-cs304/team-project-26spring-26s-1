"""Conversation-scoped event buffer with fan-out and close signalling."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

_EOF = None  # sentinel written to queues when the stream ends


class ConversationEventBuffer:
    """Fan-out buffer for one conversation stream.

    The worker writes events via ``publish()`` / ``close()``.  SSE consumers
    call ``new_subscriber()`` synchronously to register a queue *before* the
    worker starts, then iterate events via ``listen()``.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    # ------------------------------------------------------------------
    # Producer API (called by the worker)
    # ------------------------------------------------------------------

    async def publish(self, event: dict) -> None:
        """Broadcast one event to every active subscriber."""
        for queue in list(self._subscribers):
            await queue.put(event)

    async def close(self) -> None:
        """Signal end-of-stream to all subscribers."""
        for queue in list(self._subscribers):
            await queue.put(_EOF)

    # ------------------------------------------------------------------
    # Consumer API (called by SSE handler)
    # ------------------------------------------------------------------

    def new_subscriber(self) -> asyncio.Queue:
        """Register a new subscriber queue *synchronously* and return it.

        Must be called before ``worker.start()`` so no events are missed.
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def remove_subscriber(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    async def listen(self, queue: asyncio.Queue) -> AsyncIterator[dict]:
        """Yield events from *queue* until the end-of-stream sentinel."""
        try:
            while True:
                item = await queue.get()
                if item is _EOF:
                    return
                yield item
        finally:
            self.remove_subscriber(queue)
