from typing import TypedDict

from langgraph.prebuilt import ToolNode


class ToolArtifact(TypedDict):
    break_agent_loop: bool

from .core_memory import core_memory_insert
from .code_interpreter import python_interpreter

tools = [
    core_memory_insert,
    python_interpreter
]

tool_node = ToolNode(tools=tools)