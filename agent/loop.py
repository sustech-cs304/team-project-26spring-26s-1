"""Reusable agent loop extracted from the CLI entry-point.

The ``AgentLoop`` class owns every tool / service instance and exposes a
single ``step()`` method that takes a conversation context (message list),
appends the user turn, runs the model (with tool-call follow-ups), performs
eviction / fold maintenance, and returns the *updated* context together with
the assistant's final text response.

This design is intentionally stateless with respect to any single
conversation — all mutable state lives in the ``messages`` list that the
caller passes in and gets back.  The loop can therefore serve many
concurrent conversations simply by maintaining one ``messages`` list per
conversation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

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


# ── Value objects returned by step() ─────────────────────────────────────────


@dataclass
class ToolCallRecord:
    """A single tool invocation that happened during the step."""

    name: str
    arguments: dict
    result: str


@dataclass
class StepResult:
    """Everything produced by a single ``AgentLoop.step()`` call."""

    response: str
    """The assistant's final text reply."""

    messages: list[dict]
    """The full, updated conversation context (including the new turns)."""

    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    """Ordered list of tool calls that were executed during this step."""


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
        self.agent_client = openai.AsyncOpenAI(
            base_url=cfg.agent_api_base_url, api_key=cfg.agent_api_key
        )
        self.utility_client = openai.AsyncOpenAI(
            base_url=cfg.utility_api_base_url, api_key=cfg.utility_api_key
        )
        self.embed_client = openai.AsyncOpenAI(
            base_url=cfg.embed_api_base_url, api_key=cfg.embed_api_key
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
    # Core loop
    # ------------------------------------------------------------------

    async def _call_model(self, messages: list[dict]):
        """Single OpenAI chat-completion call."""
        return await self.agent_client.chat.completions.create(
            model=self.config.agent_model,
            messages=messages,  # type: ignore[arg-type]
            tools=self.tools.openai_format(),  # type: ignore[arg-type]
        )

    async def step(self, messages: list[dict], user_input: str) -> StepResult:
        """Run one full user→assistant turn (including any tool-call loops).

        Parameters
        ----------
        messages:
            The current conversation context.  **Not mutated** — a new list is
            returned inside the ``StepResult``.
        user_input:
            The latest message from the user.

        Returns
        -------
        StepResult
            Contains the assistant's final text, the updated message list, and
            a log of every tool call executed.
        """
        # Work on a shallow copy so the caller's list is not mutated.
        messages = list(messages)

        # Refresh system message and append the user turn.
        messages[0]["content"] = self.ctx_manager.build_system_message()
        messages.append({"role": "user", "content": user_input})

        tool_call_log: list[ToolCallRecord] = []

        # Agent loop: keep going while the model wants to call tools.
        while True:
            messages[0]["content"] = self.ctx_manager.build_system_message()
            response = await self._call_model(messages)
            choice = response.choices[0]

            if choice.message.tool_calls:
                messages.append(choice.message.model_dump())
                for tc in choice.message.tool_calls:
                    args = json.loads(tc.function.arguments)  # type: ignore[union-attr]
                    result = await self.tools.run_tool(tc.function.name, args)  # type: ignore[union-attr]
                    tool_call_log.append(
                        ToolCallRecord(name=tc.function.name, arguments=args, result=result)  # type: ignore[union-attr]
                    )
                    tool_call_str = (
                        f"Calling tool: {tc.function.name} with arguments {args}"  # type: ignore[union-attr]
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": f"{tool_call_str}: {result}",
                        }
                    )
            else:
                assistant_text = choice.message.content or ""
                messages.append(choice.message.model_dump())
                break

        # Maintenance passes (operate on the list in-place).
        await self.ctx_manager.run_eviction()
        await self.ctx_manager.run_fold(messages)

        return StepResult(
            response=assistant_text,
            messages=messages,
            tool_calls=tool_call_log,
        )
