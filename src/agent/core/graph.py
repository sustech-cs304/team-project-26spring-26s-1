from typing import cast

from langgraph.graph import END, START, StateGraph
from langchain.messages import AIMessage, ToolMessage
from langgraph.prebuilt.tool_node import ToolCallWithContext
from agent.nodes.context_compacting import context_compacting_node
from agent.nodes.mcp_tool import MCPToolNode
from agent.nodes.model import ConfiguredModel
from agent.nodes.user_input import user_input_node
from agent.core.state import AgentState
from agent.services.mcp_lifespan import MCPLifespanManager
from agent.tools import (
    ToolArtifact,
    internal_tool_names,
    tool_node,
    tools as agent_tools,
)
from langgraph.types import Send
from langgraph.store.base import BaseStore
from langgraph.checkpoint.base import BaseCheckpointSaver


def _make_tool_route(no_tool_route: str):
    async def tool_route(state: AgentState):
        messages = state.get("messages", [])
        if not messages:
            return no_tool_route
        last_message = messages[-1]
        if not isinstance(last_message, AIMessage):
            return no_tool_route
        tool_calls = last_message.tool_calls
        if not tool_calls:
            return no_tool_route
        return [
            Send(
                "tool_node" if tool_call["name"] in internal_tool_names else "mcp_tool_node",
                ToolCallWithContext(
                    __type="tool_call_with_context",
                    tool_call=tool_call,
                    state=state
                ),
            )
            for tool_call in tool_calls
        ]

    return tool_route


def _make_tool_result_route(break_route: str):
    async def tool_result_route(state: AgentState):
        messages = state.get("messages", [])
        if not messages:
            return break_route

        trailing_tool_messages = []
        for message in reversed(messages):
            if isinstance(message, ToolMessage):
                trailing_tool_messages.append(message)
            else:
                break

        for message in trailing_tool_messages:
            if isinstance(message.artifact, dict):
                artifact = cast(ToolArtifact, message.artifact)
                if artifact.get("break_agent_loop", False):
                    return break_route

        return "context_compacting"

    return tool_result_route


async def create_graph(
    store: BaseStore,
    checkpointer: BaseCheckpointSaver,
    mcp_manager: MCPLifespanManager,
):
    workflow = StateGraph(AgentState)

    model = ConfiguredModel(tools=agent_tools, mcp_manager=mcp_manager)
    mcp_tool_node = MCPToolNode(mcp_manager)

    workflow.add_node("user_input", user_input_node)
    workflow.add_node("context_compacting", context_compacting_node)
    workflow.add_node("chat", model.invoke_node)
    workflow.add_node("tool_node", tool_node)
    workflow.add_node("mcp_tool_node", mcp_tool_node)
    workflow.add_edge(START, "user_input")
    workflow.add_edge("user_input", "context_compacting")
    workflow.add_edge("context_compacting", "chat")
    workflow.add_conditional_edges("chat", _make_tool_route("user_input"))
    workflow.add_conditional_edges("tool_node", _make_tool_result_route("user_input"))
    workflow.add_conditional_edges("mcp_tool_node", _make_tool_result_route("user_input"))

    graph = workflow.compile(store=store, checkpointer=checkpointer)
    return graph


def create_subagent_graph():
    workflow = StateGraph(AgentState)

    model = ConfiguredModel(tools=agent_tools)

    workflow.add_node("context_compacting", context_compacting_node)
    workflow.add_node("chat", model.invoke_node)
    workflow.add_node("tool_node", tool_node)

    workflow.add_edge(START, "context_compacting")
    workflow.add_edge("context_compacting", "chat")
    workflow.add_conditional_edges("chat", _make_tool_route(END))
    workflow.add_conditional_edges("tool_node", _make_tool_result_route(END))

    return workflow.compile(store=None, checkpointer=False)
