from typing import cast

from langgraph.graph import START, StateGraph
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

async def create_graph(
    store: BaseStore,
    checkpointer: BaseCheckpointSaver,
    mcp_manager: MCPLifespanManager,
):
    workflow = StateGraph(AgentState)
    
    model = ConfiguredModel(tools=agent_tools, mcp_manager=mcp_manager)
    mcp_tool_node = MCPToolNode(mcp_manager)
    
    async def tool_route(state: AgentState):
        messages = state.get("messages", [])
        if not messages:
            return "user_input"
        last_message = messages[-1]
        if not isinstance(last_message, AIMessage):
            return "user_input"
        tool_calls = last_message.tool_calls
        if not tool_calls:
            return "user_input"
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

    async def tool_result_route(state: AgentState):
        messages = state.get("messages", [])
        if not messages:
            return "user_input"

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
                    return "user_input"

        return "context_compacting"
    
    workflow.add_node("user_input", user_input_node)
    workflow.add_node("context_compacting", context_compacting_node)
    workflow.add_node("chat", model.invoke_node)
    workflow.add_node("tool_node", tool_node)
    workflow.add_node("mcp_tool_node", mcp_tool_node)
    workflow.add_edge(START, "user_input")
    workflow.add_edge("user_input", "context_compacting")
    workflow.add_edge("context_compacting", "chat")
    workflow.add_conditional_edges("chat", tool_route)
    workflow.add_conditional_edges("tool_node", tool_result_route)
    workflow.add_conditional_edges("mcp_tool_node", tool_result_route)

    graph = workflow.compile(store=store, checkpointer=checkpointer)
    return graph
    
