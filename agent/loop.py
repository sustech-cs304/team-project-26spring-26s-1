"""Reusable agent loop extracted from the CLI entry-point.

The ``AgentLoop`` class owns every tool / service instance and exposes a
streaming ``step()`` async-generator that takes a conversation context
(message list), appends the user turn, runs the model (with tool-call
follow-ups), performs eviction / fold maintenance, and **yields**
``StreamEvent`` objects as they occur.

This design is intentionally stateless with respect to any single
conversation — all mutable state lives in the ``messages`` list that the
caller passes in.  The loop can therefore serve many concurrent
conversations simply by maintaining one ``messages`` list per conversation.

Streaming event types
---------------------
* ``ReasoningEvent``   – a chunk of the model's internal reasoning / thinking
* ``TextDeltaEvent``   – a chunk of the assistant's visible reply
* ``ToolCallStartEvent`` – a tool invocation is about to start
* ``ToolResultEvent``  – a tool invocation completed
* ``DoneEvent``        – the turn is finished; carries the full updated
  message list and aggregated metadata
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import AsyncGenerator, Union

import httpx
import openai
from qdrant_client import AsyncQdrantClient

from .code_runner import CodeRunnerBase, create_code_runner
from .config import Config
from .context_manager import ContextManager
from .core_memory import CoreMemory
from .mem0 import Mem0
from .rag import KnowledgeBase
from .skills import SkillsStore
from .tools import Tools


# ── Streaming events yielded by step() ───────────────────────────────────────


@dataclass
class ReasoningEvent:
    """A chunk of the model's chain-of-thought / thinking trace."""

    delta: str


@dataclass
class TextDeltaEvent:
    """A chunk of the assistant's visible reply text."""

    delta: str


@dataclass
class ToolCallStartEvent:
    """Emitted when a tool invocation begins."""

    name: str
    arguments: dict


@dataclass
class ToolResultEvent:
    """Emitted when a tool invocation completes."""

    name: str
    arguments: dict
    result: str


@dataclass
class DoneEvent:
    """Final event — the turn is complete."""

    response: str
    """The full assistant text reply (concatenated from all TextDeltaEvents)."""

    messages: list[dict]
    """The updated conversation context (including the new turns)."""

    tool_calls: list[ToolResultEvent] = field(default_factory=list)
    """Ordered list of tool calls that were executed during this step."""

    reasoning: str = ""
    """Full concatenated reasoning trace."""


StreamEvent = Union[
    ReasoningEvent, TextDeltaEvent, ToolCallStartEvent, ToolResultEvent, DoneEvent
]


# ── HTTP client factory (system-proxy aware) ─────────────────────────────────

def _make_http_client() -> httpx.AsyncClient:
    """Return an AsyncClient that forwards system proxy settings to openai.

    The openai library does not read Windows system proxies by default.
    We detect them via urllib.request.getproxies() and fall back to the
    HTTPS_PROXY / HTTP_PROXY environment variables if set.
    """
    proxy_url: str | None = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("http_proxy")
        or urllib.request.getproxies().get("https")
        or urllib.request.getproxies().get("http")
    )
    if proxy_url:
        return httpx.AsyncClient(proxy=proxy_url, timeout=120)
    return httpx.AsyncClient(timeout=120)


# ── Legacy compat ────────────────────────────────────────────────────────────


@dataclass
class ToolCallRecord:
    """A single tool invocation that happened during the step."""

    name: str
    arguments: dict
    result: str


@dataclass
class StepResult:
    """Aggregated result — available via :meth:`AgentLoop.step_full`."""

    response: str
    """The assistant's final text reply."""

    messages: list[dict]
    """The full, updated conversation context (including the new turns)."""

    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    """Ordered list of tool calls that were executed during this step."""

    reasoning: list[str] = field(default_factory=list)
    """Reasoning / thinking traces emitted by the model during this step."""


# ── The loop itself ──────────────────────────────────────────────────────────


class AgentLoop:
    """Owns all tool instances and drives the agent's reasoning loop.

    Typical lifecycle::

        loop = await AgentLoop.create()  # one-time async setup
        ctx  = loop.new_context()        # per-conversation

        result = loop.step(ctx, "Hello!")
        ctx = result.messages       # carry forward

        result = loop.step(ctx, "What is 2 + 2?")
        ctx = result.messages

        await loop.save_memory(ctx)       # persist long-term memory
        await loop.shutdown()             # clean up resources
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config.from_yaml()
        cfg = self.config

        # ── OpenAI clients ───────────────────────────────────────────
        # Build an httpx transport that respects system proxies.
        # The openai library does not read Windows system proxy settings on its
        # own, so we forward them explicitly via http_client.
        _http_client = _make_http_client()
        self.agent_client = openai.AsyncOpenAI(
            base_url=cfg.agent_api_base_url,
            api_key=cfg.agent_api_key,
            http_client=_http_client,
        )
        self.utility_client = openai.AsyncOpenAI(
            base_url=cfg.utility_api_base_url,
            api_key=cfg.utility_api_key,
            http_client=_make_http_client(),
        )
        self.embed_client = openai.AsyncOpenAI(
            base_url=cfg.embed_api_base_url,
            api_key=cfg.embed_api_key,
            http_client=_make_http_client(),
        )

        # ── Tool registry ────────────────────────────────────────────
        self.tools = Tools()

        cfg.agent_qdrant_path.mkdir(parents=True, exist_ok=True)
        self.agent_qdrant = AsyncQdrantClient(path=str(cfg.agent_qdrant_path))

        # Type declarations for attributes initialised by create().
        # Assignments happen there after async resources are ready.
        self.longterm_memory: Mem0
        self.core_memory: CoreMemory
        self.knowledge_base: KnowledgeBase
        self.skills_store: SkillsStore
        self.code_runner: CodeRunnerBase
        self.ctx_manager: ContextManager

    @classmethod
    async def create(cls, config: Config | None = None) -> "AgentLoop":
        """Async factory — use this instead of direct instantiation.

        Awaits the initialisation of async-backed resources (Mem0 / Qdrant)
        and wires all tools before returning a fully ready instance.
        """
        instance = cls(config)
        cfg = instance.config

        instance.longterm_memory = await Mem0.create(config=cfg, client=instance.utility_client)
        instance.tools.register("longterm_memory", instance.longterm_memory.get_tools())

        instance.core_memory = CoreMemory(config=cfg, mem0=instance.longterm_memory)
        instance.tools.register("core_memory", instance.core_memory.get_tools())

        instance.knowledge_base = KnowledgeBase(
            config=cfg, client=instance.embed_client, qdrant=instance.agent_qdrant
        )
        instance.tools.register("knowledge_base", instance.knowledge_base.get_tools())

        instance.skills_store = SkillsStore(
            config=cfg, client=instance.embed_client, qdrant=instance.agent_qdrant
        )
        instance.tools.register("skills", instance.skills_store.get_tools())

        instance.code_runner = create_code_runner(config=cfg, client=instance.utility_client)
        instance.tools.register("code_runner", instance.code_runner.get_tools())

        # ── Context manager ──────────────────────────────────────────
        instance.ctx_manager = ContextManager(
            config=cfg,
            core_memory=instance.core_memory,
            tools=instance.tools,
            client=instance.agent_client,
            model=cfg.agent_model,
        )

        return instance

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def new_context(self) -> list[dict]:
        """Return a fresh conversation context (system message only)."""
        return [{"role": "system", "content": self.ctx_manager.build_system_message()}]

    async def save_memory(self, messages: list[dict]) -> None:
        """Persist the conversation into long-term memory."""
        await self.longterm_memory.insert_memory(messages)

    async def shutdown(self) -> None:
        """Release heavyweight resources (qdrant handles, sandbox, …)."""
        try:
            self.code_runner.cleanup()
        except Exception:
            pass
        try:
            await self.agent_qdrant.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Core loop  (streaming async generator)
    # ------------------------------------------------------------------

    async def step(
        self, messages: list[dict], user_input: str
    ) -> AsyncGenerator[StreamEvent, None]:
        """Run one full user→assistant turn, **streaming** events as they happen.

        Parameters
        ----------
        messages:
            The current conversation context.  **Not mutated** — a new list is
            built internally and delivered inside the final ``DoneEvent``.
        user_input:
            The latest message from the user.

        Yields
        ------
        StreamEvent
            ``ReasoningEvent`` / ``TextDeltaEvent`` / ``ToolCallStartEvent`` /
            ``ToolResultEvent`` during the turn, then a final ``DoneEvent``.
        """
        # Work on a shallow copy so the caller's list is not mutated.
        messages = list(messages)

        # Refresh system message and append the user turn.
        messages[0]["content"] = self.ctx_manager.build_system_message()
        messages.append({"role": "user", "content": user_input})

        tool_call_log: list[ToolResultEvent] = []
        reasoning_parts: list[str] = []
        assistant_text = ""

        # Agent loop: keep going while the model wants to call tools.
        while True:
            messages[0]["content"] = self.ctx_manager.build_system_message()

            # ── streaming completion request ─────────────────────────
            stream = await self.agent_client.chat.completions.create(
                model=self.config.agent_model,
                messages=messages,  # type: ignore[arg-type]
                tools=self.tools.openai_format(),  # type: ignore[arg-type]
                stream=True,
            )

            # Accumulators for this single completion
            current_reasoning = ""
            current_content = ""
            tool_calls_in_progress: dict[int, dict] = {}  # index → {id, name, arguments_str}

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is None:
                    continue

                # Reasoning / thinking stream
                reasoning_piece = getattr(delta, "reasoning_content", None) or ""
                if reasoning_piece:
                    current_reasoning += reasoning_piece
                    yield ReasoningEvent(delta=reasoning_piece)

                # Content text stream
                if delta.content:
                    current_content += delta.content
                    yield TextDeltaEvent(delta=delta.content)

                # Tool call chunks (streamed incrementally)
                if delta.tool_calls:
                    for tc_chunk in delta.tool_calls:
                        idx = tc_chunk.index
                        if idx not in tool_calls_in_progress:
                            tool_calls_in_progress[idx] = {
                                "id": tc_chunk.id or "",
                                "name": (tc_chunk.function.name if tc_chunk.function and tc_chunk.function.name else ""),
                                "arguments_str": "",
                            }
                        entry = tool_calls_in_progress[idx]
                        if tc_chunk.id:
                            entry["id"] = tc_chunk.id
                        if tc_chunk.function:
                            if tc_chunk.function.name:
                                entry["name"] = tc_chunk.function.name
                            if tc_chunk.function.arguments:
                                entry["arguments_str"] += tc_chunk.function.arguments

                finish_reason = chunk.choices[0].finish_reason if chunk.choices else None

            # ── Post-stream processing ───────────────────────────────

            if current_reasoning:
                reasoning_parts.append(current_reasoning)

            if tool_calls_in_progress:
                # Build an assistant message with tool_calls for the context
                tc_entries = []
                for idx in sorted(tool_calls_in_progress):
                    entry = tool_calls_in_progress[idx]
                    tc_entries.append(
                        {
                            "id": entry["id"],
                            "type": "function",
                            "function": {
                                "name": entry["name"],
                                "arguments": entry["arguments_str"],
                            },
                        }
                    )
                assistant_msg: dict = {
                    "role": "assistant",
                    "content": current_content or None,
                    "tool_calls": tc_entries,
                }
                messages.append(assistant_msg)

                # Execute each tool and yield events
                for idx in sorted(tool_calls_in_progress):
                    entry = tool_calls_in_progress[idx]
                    args = json.loads(entry["arguments_str"])

                    yield ToolCallStartEvent(name=entry["name"], arguments=args)

                    result = await self.tools.run_tool(entry["name"], args)

                    evt = ToolResultEvent(name=entry["name"], arguments=args, result=result)
                    tool_call_log.append(evt)
                    yield evt

                    tool_call_str = (
                        f"Calling tool: {entry['name']} with arguments {args}"
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": entry["id"],
                            "content": f"{tool_call_str}: {result}",
                        }
                    )
            else:
                # No tool calls → final assistant reply
                assistant_text = current_content
                messages.append({"role": "assistant", "content": assistant_text})
                break

        # Maintenance passes (operate on the list in-place).
        await self.ctx_manager.run_eviction()
        await self.ctx_manager.run_fold(messages)

        yield DoneEvent(
            response=assistant_text,
            messages=messages,
            tool_calls=tool_call_log,
            reasoning="".join(reasoning_parts),
        )

    # ------------------------------------------------------------------
    # Convenience: non-streaming wrapper
    # ------------------------------------------------------------------

    async def step_full(self, messages: list[dict], user_input: str) -> StepResult:
        """Run one turn and return an aggregated ``StepResult`` (non-streaming).

        This is a thin wrapper around :meth:`step` for callers that do not
        need incremental streaming.
        """
        tool_calls: list[ToolCallRecord] = []
        reasoning_parts: list[str] = []
        done: DoneEvent | None = None

        async for event in self.step(messages, user_input):
            if isinstance(event, ToolResultEvent):
                tool_calls.append(
                    ToolCallRecord(name=event.name, arguments=event.arguments, result=event.result)
                )
            elif isinstance(event, ReasoningEvent):
                reasoning_parts.append(event.delta)
            elif isinstance(event, DoneEvent):
                done = event

        assert done is not None
        return StepResult(
            response=done.response,
            messages=done.messages,
            tool_calls=tool_calls,
            reasoning=reasoning_parts if reasoning_parts else [],
        )
