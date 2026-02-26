import json
from openai import OpenAI

from .config import (
    CORE_MEMORY_TOKEN_LIMIT,
    CONTEXT_TOKEN_LIMIT,
    FOLD_TRIGGER_RATIO,
    FOLD_FRACTION,
    jinja_env,
    tokenizer,
)
from .core_memory import CoreMemory
from .tools import Tools

_tmpl_system   = jinja_env.get_template("system_message.j2")
_tmpl_eviction = jinja_env.get_template("eviction_prompt.j2")
_tmpl_extract  = jinja_env.get_template("fold_extract.j2")
_tmpl_summary  = jinja_env.get_template("fold_summary.j2")


class ContextManager:
    """
    Owns all context management operations for the agentic loop:
    - System message rendering (with live core memory injection)
    - Core memory eviction (out-of-band, token-budget-driven)
    - Conversation history folding (extract facts → summarise → replace)

    All out-of-band operations are invisible to the main messages list and
    print progress prefixed with a bracketed tag for operator visibility.
    Tuning parameters are centralised in config.py.
    """

    def __init__(
        self,
        core_memory: CoreMemory,
        tools: Tools,
        client: OpenAI,
        model: str,
    ) -> None:
        self.core_memory        = core_memory
        self.tools              = tools
        self.client             = client
        self.model              = model
        self.core_memory_limit  = CORE_MEMORY_TOKEN_LIMIT
        self.context_limit      = CONTEXT_TOKEN_LIMIT
        self.fold_trigger_ratio = FOLD_TRIGGER_RATIO
        self.fold_fraction      = FOLD_FRACTION

    # ------------------------------------------------------------------
    # System message
    # ------------------------------------------------------------------

    def build_system_message(self) -> str:
        """Render the system prompt with the current core memory contents."""
        return _tmpl_system.render(
            core_memory=self.core_memory.format_memory(),
            token_limit=self.core_memory_limit,
        )

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def count_tokens(self, messages: list[dict]) -> int:
        """Approximate token count across a message list using cl100k_base."""
        total = 0
        for m in messages:
            content = m.get("content") or ""
            if isinstance(content, str):
                total += len(tokenizer.encode(content))
            total += 4  # per-message role/structure overhead
        return total

    # ------------------------------------------------------------------
    # Core memory eviction
    # ------------------------------------------------------------------

    def run_eviction(self) -> None:
        """
        Out-of-band core memory eviction pass. When core memory exceeds its
        token budget, repeatedly asks the model to archive the lowest-priority
        key until the budget is satisfied or the model declines.

        Out-of-band: uses an ephemeral message list; never touches the main
        conversation history.
        """
        if self.core_memory.token_count() <= self.core_memory_limit:
            return

        archive_tool = [
            t for t in self.tools.openai_format()
            if t["function"]["name"] == "core_memory_archive"
        ]

        for _ in range(len(self.core_memory.memory)):
            if self.core_memory.token_count() <= self.core_memory_limit:
                break
            prompt = _tmpl_eviction.render(
                token_count=self.core_memory.token_count(),
                token_limit=self.core_memory_limit,
                core_memory=self.core_memory.format_memory(),
            )
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                tools=archive_tool,
            )
            if not response.choices[0].message.tool_calls:
                print("[Memory eviction] Model declined to archive further.")
                break
            for tool_call in response.choices[0].message.tool_calls:
                if tool_call.function.name == "core_memory_archive":
                    args = json.loads(tool_call.function.arguments)
                    result = self.tools.run_tool("core_memory_archive", args)
                    print(f"[Memory eviction] core_memory_archive({args}): {result}")

    # ------------------------------------------------------------------
    # Conversation history fold
    # ------------------------------------------------------------------

    def run_fold(self, messages: list[dict]) -> None:
        """
        Out-of-band hybrid context fold. Triggered when the history token count
        exceeds FOLD_TRIGGER_RATIO * CONTEXT_TOKEN_LIMIT.

        Steps:
        1. Identify the oldest FOLD_FRACTION of non-system messages.
        2. Extract salient facts from the segment into long-term memory.
        3. Summarise the segment into a concise narrative.
        4. Replace the folded messages with the summary in-place (messages is
           mutated directly so the caller's list is updated).

        Out-of-band: the two LLM calls use ephemeral message lists and are
        never injected into the main conversation history.
        """
        if self.count_tokens(messages) < self.context_limit * self.fold_trigger_ratio:
            return

        non_system  = messages[1:]
        fold_count  = max(2, int(len(non_system) * self.fold_fraction))
        fold_target = non_system[:fold_count]

        dialogue = [
            m for m in fold_target
            if m["role"] in ("user", "assistant")
            and not m.get("tool_calls")
            and isinstance(m.get("content"), str)
            and m["content"].strip()
        ]
        if not dialogue:
            return

        print(
            f"[Context fold] Triggered at {self.count_tokens(messages)} tokens. "
            f"Folding {fold_count} messages."
        )

        # Step 1: extract salient facts
        insert_tool = [
            t for t in self.tools.openai_format()
            if t["function"]["name"] == "long_term_memory_insert"
        ]
        extract_response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": _tmpl_extract.render(dialogue=dialogue)}],
            tools=insert_tool,
        )
        if extract_response.choices[0].message.tool_calls:
            for tool_call in extract_response.choices[0].message.tool_calls:
                if tool_call.function.name == "long_term_memory_insert":
                    args = json.loads(tool_call.function.arguments)
                    result = self.tools.run_tool("long_term_memory_insert", args)
                    print(f"[Context fold] long_term_memory_insert({args}): {result}")

        # Step 2: summarise
        summary_response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": _tmpl_summary.render(dialogue=dialogue)}],
        )
        summary_text = (summary_response.choices[0].message.content or "").strip()

        # Step 3: replace in-place
        del messages[1:fold_count + 1]
        messages.insert(1, {
            "role": "system",
            "content": f"[Earlier conversation summary]\n{summary_text}",
        })
        print(f"[Context fold] Done. Summary: {summary_text[:120]}...")
