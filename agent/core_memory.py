from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .config import tokenizer, CORE_MEMORY_PATH

if TYPE_CHECKING:
    from .mem0 import Mem0
    from .tools import ToolEntry


class CoreMemory:
    """
    A class to represent the core memory of the agent.
    Entries are persisted to disk so they survive process restarts.
    """

    def __init__(self, mem0: Mem0 | None = None) -> None:
        self._mem0 = mem0
        CORE_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        if CORE_MEMORY_PATH.exists():
            try:
                self.memory: dict[str, str] = json.loads(CORE_MEMORY_PATH.read_text(encoding="utf-8"))
            except Exception:
                self.memory = {}
        else:
            self.memory = {}

    def _save(self) -> None:
        CORE_MEMORY_PATH.write_text(
            json.dumps(self.memory, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def token_count(self) -> int:
        """Return the number of tokens in the formatted core memory string, using cl100k_base encoding."""
        return len(tokenizer.encode(self.format_memory()))
        
    def get_tools(self) -> list[ToolEntry]:
        """Return tool entries for registration with the Tools registry."""
        entries = [self._insert_tool(), self._modify_tool()]
        if self._mem0 is not None:
            entries.append(self._archive_tool())
        return entries

    def _insert_tool(self) -> ToolEntry:
        tool_insert = {
            "name": "core_memory_insert",
            "description": (
                "Save or append an important, persistent fact into core memory under a descriptive key. "
                "Use this to remember critical information about the user or context across the entire conversation, "
                "such as their name, occupation, preferences, goals, or any detail they explicitly share that you may need later. "
                "Choose a clear, concise key that describes the category of information (e.g., 'user_name', 'user_job', 'dietary_preferences', 'current_project'). "
                "If the key already exists, the new statement is APPENDED to the existing value — so include a separator like '; ' or ' | ' at the start of your statement if needed. "
                "To erase an existing key's value entirely, pass an empty string as the statement. "
                "Do NOT use this tool for temporary or session-specific information — only for facts that should persist long-term."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": (
                            "A short, descriptive identifier for the type of information being stored. "
                            "Use snake_case. Examples: 'user_name', 'user_age', 'user_location', 'user_preferences', "
                            "'user_goals', 'user_occupation', 'important_dates'. "
                            "Reuse existing keys when adding related information to the same category."
                        )
                    },
                    "statement": {
                        "type": "string",
                        "description": (
                            "The fact or information to store. Write it as a clear, self-contained statement "
                            "(e.g., 'Alice', 'enjoys hiking and cooking', 'working on a Python AI agent project'). "
                            "Pass an empty string to erase the existing value for this key."
                        )
                    }
                },
                "required": ["key", "statement"]
            }
        }
        def tool_func_insert(params: dict) -> str:
            if not params["statement"]:
                self.memory[params["key"]] = ""
            else:
                self.memory[params["key"]] = self.memory.get(params["key"], "") + params["statement"]
            self._save()
            return "Statement inserted into core memory." if params["statement"] else "Statement erased from core memory."
        return (tool_insert, tool_func_insert)

    def _modify_tool(self) -> ToolEntry:
        tool_modify = {
            "name": "core_memory_modify",
            "description": (
                "Update or correct an existing fact in core memory by replacing a specific substring within the stored value. "
                "Use this when the user corrects previously stored information, or when a fact needs to be updated "
                "(e.g., the user changes their name, updates their job, or corrects a preference you saved earlier). "
                "The specified key MUST already exist in core memory — use 'core_memory_insert' first if it does not. "
                "All occurrences of 'old_substring' within the stored value will be replaced with 'new_substring'. "
                "Be precise with 'old_substring' — it must match the stored text exactly (including spacing and capitalization)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": (
                            "The key of the core memory entry to modify. "
                            "This key must already exist. Examples: 'user_name', 'user_preferences', 'user_occupation'."
                        )
                    },
                    "old_substring": {
                        "type": "string",
                        "description": (
                            "The exact text within the existing stored value that you want to replace. "
                            "Must match the currently stored text character-for-character, including spaces and capitalization."
                        )
                    },
                    "new_substring": {
                        "type": "string",
                        "description": (
                            "The new text to substitute in place of 'old_substring'. "
                            "Pass an empty string to simply delete the old substring from the stored value."
                        )
                    }
                },
                "required": ["key", "old_substring", "new_substring"]
            }
        }
        def tool_func_modify(params: dict) -> str:
            if params["key"] not in self.memory:
                return "Key does not exist in core memory."
            self.memory[params["key"]] = self.memory[params["key"]].replace(params["old_substring"], params["new_substring"])
            self._save()
            return "Statement modified in core memory."
        return (tool_modify, tool_func_modify)

    def _archive_tool(self) -> ToolEntry:
        assert self._mem0 is not None
        mem0 = self._mem0
        tool_archive = {
            "name": "core_memory_archive",
            "description": (
                "Move an entry from core memory into the long-term archive (core_archive fraction), freeing up the core memory slot. "
                "Use this when a fact is still worth keeping permanently but no longer needs to occupy fast-access core memory — "
                "for example: a goal the user has completed, a project that has concluded, a decision that has been resolved, "
                "or background context that is useful to retain but unlikely to be needed in every response. "
                "The entry is written verbatim to the archive under its key, then removed from core memory. "
                "It can be retrieved later using 'long_term_memory_query' with fraction='core_archive'. "
                "Do NOT archive facts that are still actively relevant to the current conversation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": (
                            "The core memory key to archive and remove. "
                            "Must currently exist in core memory. "
                            "Examples: 'current_project', 'active_goal', 'user_occupation'."
                        )
                    }
                },
                "required": ["key"]
            }
        }
        def tool_func_archive(params: dict) -> str:
            key = params["key"]
            if key not in self.memory:
                return f"Key '{key}' does not exist in core memory."
            value = self.memory.pop(key)
            self._save()
            mem0.archive_fact(f"{key}: {value}", fraction="core_archive")
            return f"Key '{key}' archived to long-term memory (core_archive) and removed from core memory."
        return (tool_archive, tool_func_archive)

    def format_memory(self) -> str:
        """
        Format the core memory for output.
        """
        return "\n".join([f"{key}: {value}" for key, value in self.memory.items()])