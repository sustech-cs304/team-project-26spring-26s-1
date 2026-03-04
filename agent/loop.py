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
from qdrant_client import QdrantClient

from .code_runner import CodeRunner
from .config import (
    AGENT_API_BASE_URL,
    AGENT_API_KEY,
    AGENT_MODEL,
    AGENT_QDRANT_PATH,
    EMBED_API_BASE_URL,
    EMBED_API_KEY,
    USER_ID,
    UTILITY_API_BASE_URL,
    UTILITY_API_KEY,
    UTILITY_MODEL,
)
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

        loop = AgentLoop()          # one-time setup
        ctx  = loop.new_context()   # per-conversation

        result = loop.step(ctx, "Hello!")
        ctx = result.messages       # carry forward

        result = loop.step(ctx, "What is 2 + 2?")
        ctx = result.messages

        loop.save_memory(ctx)       # persist long-term memory
        loop.shutdown()             # clean up resources
    """

    def __init__(self) -> None:
        # ── OpenAI clients ───────────────────────────────────────────
        self.agent_client = openai.OpenAI(
            base_url=AGENT_API_BASE_URL, api_key=AGENT_API_KEY
        )
        self.utility_client = openai.OpenAI(
            base_url=UTILITY_API_BASE_URL, api_key=UTILITY_API_KEY
        )
        self.embed_client = openai.OpenAI(
            base_url=EMBED_API_BASE_URL, api_key=EMBED_API_KEY
        )

        # ── Tool registry ────────────────────────────────────────────
        self.tools = Tools()

        self.longterm_memory = Mem0(
            user_id=USER_ID, client=self.utility_client, model=UTILITY_MODEL
        )
        self.tools.register("longterm_memory", self.longterm_memory.get_tools())

        self.core_memory = CoreMemory(mem0=self.longterm_memory)
        self.tools.register("core_memory", self.core_memory.get_tools())

        AGENT_QDRANT_PATH.mkdir(parents=True, exist_ok=True)
        self.agent_qdrant = QdrantClient(path=str(AGENT_QDRANT_PATH))

        self.knowledge_base = KnowledgeBase(
            client=self.embed_client, qdrant=self.agent_qdrant
        )
        self.tools.register("knowledge_base", self.knowledge_base.get_tools())

        self.skills_store = SkillsStore(
            client=self.embed_client, qdrant=self.agent_qdrant
        )
        self.tools.register("skills", self.skills_store.get_tools())

        self.code_runner = CodeRunner(client=self.utility_client)
        self.tools.register("code_runner", self.code_runner.get_tools())

        # ── Context manager ──────────────────────────────────────────
        self.ctx_manager = ContextManager(
            core_memory=self.core_memory,
            tools=self.tools,
            client=self.agent_client,
            model=AGENT_MODEL,
        )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def new_context(self) -> list[dict]:
        """Return a fresh conversation context (system message only)."""
        return [{"role": "system", "content": self.ctx_manager.build_system_message()}]

    def save_memory(self, messages: list[dict]) -> None:
        """Persist the conversation into long-term memory."""
        self.longterm_memory.insert_memory(messages)

    def shutdown(self) -> None:
        """Release heavyweight resources (qdrant handles, sandbox, …)."""
        try:
            self.code_runner.cleanup()
        except Exception:
            pass
        try:
            self.agent_qdrant.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    def _call_model(self, messages: list[dict]):
        """Single OpenAI chat-completion call."""
        return self.agent_client.chat.completions.create(
            model=AGENT_MODEL,
            messages=messages,  # type: ignore[arg-type]
            tools=self.tools.openai_format(),  # type: ignore[arg-type]
        )

    def step(self, messages: list[dict], user_input: str) -> StepResult:
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
            response = self._call_model(messages)
            choice = response.choices[0]

            if choice.message.tool_calls:
                messages.append(choice.message.model_dump())
                for tc in choice.message.tool_calls:
                    args = json.loads(tc.function.arguments)  # type: ignore[union-attr]
                    result = self.tools.run_tool(tc.function.name, args)  # type: ignore[union-attr]
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
        self.ctx_manager.run_eviction()
        self.ctx_manager.run_fold(messages)

        return StepResult(
            response=assistant_text,
            messages=messages,
            tool_calls=tool_call_log,
        )
