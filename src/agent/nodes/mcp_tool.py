from __future__ import annotations

from langchain.messages import ToolMessage
from langgraph.config import get_config as get_runnable_config
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import ToolCallWithContext
from langgraph.runtime import Runtime

from agent.services.mcp_lifespan import MCPLifespanManager


class MCPToolNode:
    def __init__(self, mcp_manager: MCPLifespanManager):
        self._mcp_manager = mcp_manager

    async def __call__(
        self,
        input: ToolCallWithContext,
        runtime: Runtime,
    ) -> dict[str, list[ToolMessage]]:
        tool_call = input["tool_call"]

        try:
            tool = await self._mcp_manager.get_tool(tool_call["name"])
        except Exception as exc:
            return {
                "messages": [
                    ToolMessage(
                        content=str(exc),
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"],
                        status="error",
                    )
                ]
            }

        if tool is None:
            return {
                "messages": [
                    ToolMessage(
                        content=(
                            f"MCP tool '{tool_call['name']}' is not available."
                        ),
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"],
                        status="error",
                    )
                ]
            }

        tool_node = ToolNode([tool])
        try:
            return await tool_node._afunc(input, get_runnable_config(), runtime)
        except Exception as exc:
            return {
                "messages": [
                    ToolMessage(
                        content=str(exc),
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"],
                        status="error",
                    )
                ]
            }
