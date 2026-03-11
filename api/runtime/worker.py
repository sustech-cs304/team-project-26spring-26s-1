"""Background worker for one conversation turn."""

from __future__ import annotations

import asyncio

from api.adapters.agent_adapter import AgentAdapter
from api.buffering.event_buffer import ConversationEventBuffer
from api.runtime.cancel_token import CancelToken


class ConversationWorker:
    """Owns one background task that continues even if SSE clients disconnect."""

    def __init__(
        self,
        conversation_id: str,
        user_input: str,
        adapter: AgentAdapter,
        buffer: ConversationEventBuffer,
    ) -> None:
        self.conversation_id = conversation_id
        self.user_input = user_input
        self.adapter = adapter
        self.buffer = buffer
        self.cancel_token = CancelToken()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Schedule the worker task (no-op if already started)."""
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        """Drive the agent adapter and broadcast events to the buffer."""
        try:
            async for event in self.adapter.stream_turn(
                conversation_id=self.conversation_id,
                user_input=self.user_input,
            ):
                if self.cancel_token.is_cancelled:
                    break
                await self.buffer.publish(event)
        finally:
            await self.buffer.close()

    def cancel(self) -> None:
        self.cancel_token.cancel()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()
