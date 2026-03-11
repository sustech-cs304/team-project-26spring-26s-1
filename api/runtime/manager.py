"""In-memory runtime manager for conversation workers and buffers."""

from __future__ import annotations

import asyncio

from api.adapters.agent_adapter import AgentAdapter
from api.buffering.event_buffer import ConversationEventBuffer
from api.runtime.worker import ConversationWorker


class ConversationRuntimeManager:
    """Registry for active conversation workers and buffers."""

    def __init__(self, adapter: AgentAdapter) -> None:
        self._adapter = adapter
        self._workers: dict[str, ConversationWorker] = {}
        self._buffers: dict[str, ConversationEventBuffer] = {}

    def subscribe_to_turn(
        self, conversation_id: str, user_input: str
    ) -> tuple[asyncio.Queue, ConversationEventBuffer]:
        """Atomically subscribe and (if needed) start a new worker.

        For a **reconnect** the subscriber attaches to the live buffer
        without interrupting the running worker.  For a **new turn** a fresh
        buffer is created, the subscriber queue is registered *before* the
        worker task is scheduled, so no events can be missed.

        Returns ``(queue, buffer)``; iterate events via ``buffer.listen(queue)``.
        """
        worker = self._workers.get(conversation_id)
        if worker is not None and worker.is_running:
            # Reconnect: reuse current buffer.
            buffer = self._buffers[conversation_id]
            queue = buffer.new_subscriber()
            return queue, buffer

        # New turn: fresh buffer, register subscriber, then start task.
        buffer = ConversationEventBuffer()
        self._buffers[conversation_id] = buffer
        queue = buffer.new_subscriber()  # registered before create_task
        worker = ConversationWorker(
            conversation_id=conversation_id,
            user_input=user_input,
            adapter=self._adapter,
            buffer=buffer,
        )
        self._workers[conversation_id] = worker
        worker.start()  # asyncio.create_task — runs only after next await
        return queue, buffer

    def cancel_worker(self, conversation_id: str) -> None:
        worker = self._workers.get(conversation_id)
        if worker is not None:
            worker.cancel()
