from langgraph.prebuilt import ToolNode
from .core_memory import core_memory_insert
from .code_interpreter import python_interpreter
from .retrieve import retrieve_from_rag_db

tools = [
    core_memory_insert,
    python_interpreter,
    retrieve_from_rag_db
]

tool_node = ToolNode(tools=tools)