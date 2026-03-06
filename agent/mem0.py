from __future__ import annotations

import atexit
import json
from typing import TYPE_CHECKING

from mem0 import AsyncMemory
from openai import AsyncOpenAI

from .config import Config

if TYPE_CHECKING:
    from .tools import ToolEntry


class Mem0:
    def __init__(
        self,
        config: Config,
        client: AsyncOpenAI | None = None,
        *,
        _mem: AsyncMemory,
    ) -> None:
        self._config = config
        self._client = client
        self._model = config.utility_model
        self.user_id = config.user_id
        self._mem: AsyncMemory = _mem

        # ── Derived resources (plain / sync only) ────────────────────
        self._tmpl_conflict = config.jinja_env.get_template("conflict_resolution.j2")

        # Each fraction gets its own user_id namespace so that mem0's internal
        # conflict-resolution agent — which operates across all memories for a
        # given user_id — cannot modify or delete entries from the other fraction.
        uid = config.user_id
        self._episodic_id = f"{uid}_episodic" if uid else "episodic"
        self._archive_id = f"{uid}_core_archive" if uid else "core_archive"

    @classmethod
    async def create(cls, config: Config, client: AsyncOpenAI | None = None) -> "Mem0":
        """Async factory — use this instead of direct instantiation.

        Initialises the underlying ``AsyncMemory`` backend (which opens a
        Qdrant connection) and registers the atexit cleanup handler before
        returning a fully ready instance.
        """
        mem = await AsyncMemory.from_config(config.mem0_config)
        instance = cls(config, client, _mem=mem)
        # Register an atexit handler so the qdrant clients held by _mem are
        # flushed while library modules are still intact.
        atexit.register(instance._close_mem0)
        return instance

    # Lower candidate retrieval threshold — we cast a wider net and let the
    # LLM agent make the final keep/delete decision rather than relying on score alone.
    @property
    def _CANDIDATE_THRESHOLD(self) -> float:
        return self._config.archive_candidate_threshold

    def _close_mem0(self) -> None:
        """Explicitly close all qdrant clients held inside ``self._mem``."""
        for store_attr in ("vector_store", "_telemetry_vector_store"):
            try:
                store = getattr(self._mem, store_attr, None)
                if store is not None:
                    client = getattr(store, "client", None)
                    if client is not None:
                        client.close()
            except Exception:
                pass
    def _filter_messages(self, messages: list[dict]) -> list[dict]:
        """
        Strip everything that is not genuine conversational content before archival:
        - system messages (instructions, injected memory)
        - assistant turns that are tool calls (no natural language content)
        - tool result messages
        - any message with empty/non-string content
        Only pure user utterances and natural assistant replies are retained.
        """
        return [
            m for m in messages
            if m["role"] in ("user", "assistant")
            and not m.get("tool_calls")
            and isinstance(m.get("content"), str)
            and m["content"].strip()
        ]

    async def insert_memory(self, messages: list[dict]) -> None:
        """Archive a conversation session into the episodic long-term memory store.
        Only genuine user/assistant dialogue turns are submitted; system prompts,
        tool calls, and tool responses are filtered out before extraction."""
        filtered = self._filter_messages(messages)
        print(f"[Mem0] Inserting {len(filtered)} filtered messages into long-term memory.")
        if filtered:
            await self._mem.add(filtered, user_id=self._episodic_id)

    # Similarity score threshold above which an existing entry is considered
    # a conflict with an incoming verbatim write and will be deleted first.
    # mem0 returns cosine similarity in [0, 1]; 0.82 catches same-fact
    # paraphrases while avoiding false positives on related-but-distinct facts.
    _CONFLICT_THRESHOLD: float = 0.82

    async def archive_fact(self, fact: str, fraction: str = "core_archive") -> None:
        """Directly store a verbatim fact string into the archive without LLM extraction.

        Runs a two-stage conflict resolution pass before writing:
        1. Vector search retrieves candidates above _CANDIDATE_THRESHOLD.
        2. An LLM agent reviews each candidate and decides whether to delete it
           (contradicts/duplicates/superseded) or keep it (distinct information).
        This avoids both the false-positive risk of pure score thresholds and the
        silent accumulation problem of unguarded infer=False writes.
        """
        ns = self._archive_id if fraction == "core_archive" else self._episodic_id

        # Stage 1: retrieve candidates above the lower threshold
        existing = await self._mem.search(fact, user_id=ns)
        candidates = [
            item for item in existing.get("results", [])
            if item.get("score", 0) >= self._CANDIDATE_THRESHOLD
        ]

        # Stage 2: LLM agent decides which candidates to delete
        if candidates and self._client and self._model:
            prompt = self._tmpl_conflict.render(new_fact=fact, candidates=candidates)
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            raw = (response.choices[0].message.content or "{}").strip()
            try:
                decision = json.loads(raw)
                for entry_id in decision.get("delete_ids", []):
                    await self._mem.delete(entry_id)
            except (json.JSONDecodeError, KeyError):
                pass  # if parsing fails, write anyway — better a duplicate than a silent drop

        await self._mem.add(fact, user_id=ns, infer=False)

    def get_tools(self) -> list[ToolEntry]:
        """Return long-term memory tool entries for registration."""
        return [self._query_tool(), self._insert_tool()]

    def _query_tool(self) -> ToolEntry:
        tool_query = {
            "name": "long_term_memory_query",
            "description": (
                "Search the long-term memory store for distilled facts from past conversations or explicitly archived core memory entries. "
                "The store is divided into two fractions:\n"
                "  - 'core_archive': high-confidence facts you explicitly archived from core memory — prefer this for reliable, agent-curated facts.\n"
                "  - 'episodic': facts automatically extracted from past conversation sessions by the memory system — broader but noisier.\n"
                "  - 'all': search both fractions simultaneously (default).\n"
                "Use this proactively at the start of every new conversation with fraction='all' and a broad query to surface relevant context. "
                "Use fraction='core_archive' when you need a specific, reliable fact you previously archived. "
                "The search is semantic — use descriptive phrases, not keywords."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural language description of the fact or topic to retrieve. "
                            "Use descriptive phrases rather than single keywords. "
                            "Examples: 'user dietary restrictions and food preferences', "
                            "'user preferred programming language and tools', "
                            "'user background, occupation, and interests'."
                        )
                    },
                    "fraction": {
                        "type": "string",
                        "enum": ["all", "core_archive", "episodic"],
                        "description": (
                            "Which fraction to search. "
                            "'core_archive': only explicitly archived, agent-curated facts (higher reliability). "
                            "'episodic': only auto-extracted conversational facts (broader coverage). "
                            "'all': both fractions. Default: 'all'."
                        )
                    }
                },
                "required": ["query"]
            }
        }
        async def tool_func_query(params: dict) -> str:
            fraction = params.get("fraction", "all")
            if fraction == "core_archive":
                namespaces = [self._archive_id]
            elif fraction == "episodic":
                namespaces = [self._episodic_id]
            else:
                namespaces = [self._archive_id, self._episodic_id]
            results_str = ""
            for ns in namespaces:
                results = await self._mem.search(params["query"], user_id=ns)
                results_str += "\n".join([item["memory"] for item in results["results"]])
                if results["results"]:
                    results_str += "\n"
            results_str = results_str.strip()
            return results_str if results_str else "No relevant facts found."
        return (tool_query, tool_func_query)

    def _insert_tool(self) -> ToolEntry:
        tool_insert = {
            "name": "long_term_memory_insert",
            "description": (
                "Write a single fact directly into the long-term archive (core_archive fraction) "
                "WITHOUT occupying a core memory slot. "
                "Use this to persist important information that does not need to sit in fast-access core memory right now — "
                "such as completed tasks, resolved decisions, background context you have inferred, "
                "or anything the user explicitly asks you to remember long-term. "
                "Unlike 'core_memory_insert', this bypasses the core memory tier entirely. "
                "The fact is stored verbatim as a single, self-contained statement without further LLM extraction."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {
                        "type": "string",
                        "description": (
                            "A single, complete, self-contained fact written so it makes sense when retrieved later without any additional context. "
                            "Examples: 'User completed onboarding on 2026-02-26', "
                            "'User decided to use PostgreSQL for their project database', "
                            "'User mentioned their cat is named Luna'."
                        )
                    }
                },
                "required": ["fact"]
            }
        }
        async def tool_func_insert(params: dict) -> str:
            await self.archive_fact(params["fact"], fraction="core_archive")
            return "Fact written directly to long-term archive (core_archive)."
        return (tool_insert, tool_func_insert)