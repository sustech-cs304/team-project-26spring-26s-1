from __future__ import annotations

import asyncio

import pytest

from agent.tools.sleep import sleep


pytestmark = pytest.mark.unit


def test_sleep_tool_returns_after_short_wait():
    result = asyncio.run(sleep.ainvoke({"seconds": 0.01}))

    assert result == "Slept for 0.01 seconds."


def test_sleep_tool_can_be_cancelled():
    async def _scenario():
        task = asyncio.create_task(sleep.ainvoke({"seconds": 5}))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(_scenario())
