import asyncio
from typing import Any

from langchain.messages import HumanMessage
from langchain.tools import tool
from pydantic import BaseModel, Field

from agent.core.state import AgentState


class SubagentInput(BaseModel):
    request: str = Field(
        min_length=1,
        description="Self-contained request for a non-interactive subagent.",
    )


_graph: Any | None = None
_graph_lock = asyncio.Lock()


async def _get_graph():
    global _graph
    if _graph is not None:
        return _graph

    async with _graph_lock:
        if _graph is None:
            from agent.core.graph import create_subagent_graph

            _graph = create_subagent_graph()
        return _graph


def _content_text(content: object) -> str:
    if isinstance(content, str):
        return content

    if not isinstance(content, list):
        return str(content)

    parts: list[str] = []
    for chunk in content:
        if isinstance(chunk, str):
            parts.append(chunk)
            continue
        if not isinstance(chunk, dict):
            continue
        text = chunk.get("text")
        if text is not None:
            parts.append(str(text))
            continue
        if chunk.get("type") in {"text", "output_text"} and chunk.get("content") is not None:
            parts.append(str(chunk["content"]))

    return "".join(parts)


@tool("create_subagent", args_schema=SubagentInput, extras={"hide_from_subagent": True})
async def create_subagent(request: str) -> str:
    """Run a non-interactive subagent on a self-contained request and return its final response."""
    graph = await _get_graph()
    state: AgentState = {
        "messages": [HumanMessage(role="user", content=request)],
    }
    result = await graph.ainvoke(
        state,
        config={
            "configurable": {
                "non_interactive": True,
                "subagent": True,
            },
        },
    )
    messages = result.get("messages", [])
    if not messages:
        return ""
    return _content_text(messages[-1].content).strip()


create_subagent.metadata = {"hide_from_subagent": True}
