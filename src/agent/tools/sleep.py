from __future__ import annotations

import asyncio

from langchain.tools import tool
from pydantic import BaseModel, Field


class SleepInput(BaseModel):
    seconds: float = Field(
        gt=0,
        le=60,
        description="How long to pause, in seconds. Keep this short so the agent can resume quickly.",
    )
    reason: str | None = Field(
        default=None,
        max_length=200,
        description="Optional short reason for the pause.",
    )


@tool("sleep", args_schema=SleepInput)
async def sleep(seconds: float, reason: str | None = None) -> str:
    """Pause execution for a short time and resume in the same conversation.

    Use this tool when a brief delay is needed before checking state again,
    waiting for an external side effect, or giving another tool time to settle.
    Do not use it for long waits or background scheduling.
    """
    await asyncio.sleep(seconds)
    if reason:
        return f"Slept for {seconds:g} seconds: {reason.strip()}"
    return f"Slept for {seconds:g} seconds."
