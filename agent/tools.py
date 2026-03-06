from __future__ import annotations

import inspect
from typing import Any, Callable, Coroutine, Union

ToolFunc = Union[Callable[[dict], str], Callable[[dict], Coroutine[Any, Any, str]]]
ToolEntry = tuple[dict, ToolFunc]


class Tools:
    """Registry of agent tools, organised by module.

    Modules provide their tools as a list of ``(schema, func)`` pairs via
    their ``get_tools()`` method.  The main loop registers them with::

        tools.register("core_memory", core_memory.get_tools())

    The registry tracks which module owns which tools so that an entire
    module can be unloaded cleanly with ``tools.unregister("core_memory")``.
    """

    def __init__(self) -> None:
        # module_name -> list of tool names belonging to that module
        self._modules: dict[str, list[str]] = {}
        # tool_name -> (schema, func)
        self._tools: dict[str, ToolEntry] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, module: str, entries: list[ToolEntry]) -> None:
        """Load all tools provided by *module*, replacing any previous load."""
        if module in self._modules:
            self.unregister(module)
        names: list[str] = []
        for schema, func in entries:
            name = schema["name"]
            self._tools[name] = (schema, func)
            names.append(name)
        self._modules[module] = names

    def unregister(self, module: str) -> None:
        """Remove every tool that belongs to *module*."""
        for name in self._modules.pop(module, []):
            self._tools.pop(name, None)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def modules(self) -> list[str]:
        """Return the names of all currently loaded modules."""
        return list(self._modules)

    def openai_format(self) -> list[dict]:
        """Return all tools formatted for the OpenAI chat completions API."""
        return [
            {"type": "function", "function": schema}
            for schema, _ in self._tools.values()
        ]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run_tool(self, tool_name: str, params: dict) -> str:
        """Execute a tool by name and return its string result.

        Supports both sync and async tool callables.
        """
        entry = self._tools.get(tool_name)
        if entry is None:
            raise ValueError(f"Tool {tool_name} not found.")
        _, func = entry
        result = func(params)
        if inspect.isawaitable(result):
            return await result
        return result  # type: ignore[return-value]