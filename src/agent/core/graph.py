from collections.abc import Callable
from typing import cast

from langgraph.graph import START, StateGraph
from langchain.messages import AIMessage, ToolMessage
from langgraph.prebuilt.tool_node import ToolCallWithContext
from agent.config import AppConfig
from agent.nodes.model import Model
from agent.nodes.user_input import user_input_node
from agent.core.state import AgentState
from agent.tools import ToolArtifact, tools as agent_tools, tool_node
from langgraph.types import Send
from langgraph.store.base import BaseStore
from langgraph.checkpoint.base import BaseCheckpointSaver

async def create_graph(get_config: Callable[[], AppConfig], store : BaseStore, checkpointer: BaseCheckpointSaver):
    workflow = StateGraph(AgentState)
    
    model = Model.get(
        name="Agent",
        get_config=get_config,
        tools=agent_tools,
    )
    
    async def tool_route(state: AgentState):
        if not state["messages"]:
            return "user_input"
        last_message = state['messages'][-1]
        if not isinstance(last_message, AIMessage):
            return "user_input"
        tool_calls = last_message.tool_calls
        if not tool_calls:
            return "user_input"
        return [
            Send("tool_node", (
                ToolCallWithContext(
                    __type="tool_call_with_context",
                    tool_call=tool_call,
                    state=state
            )))
            for tool_call in tool_calls
        ]

    async def tool_result_route(state: AgentState):
        if not state["messages"]:
            return "user_input"

        trailing_tool_messages = []
        for message in reversed(state["messages"]):
            if isinstance(message, ToolMessage):
                trailing_tool_messages.append(message)
            else:
                break

        for message in trailing_tool_messages:
            if isinstance(message.artifact, dict):
                artifact = cast(ToolArtifact, message.artifact)
                if artifact.get("break_agent_loop", False):
                    return "user_input"

        return "chat"
    
    workflow.add_node("user_input", user_input_node)
    workflow.add_node("chat", model.invoke_node)
    workflow.add_node("tool_node", tool_node)
    workflow.add_edge(START, "user_input")
    workflow.add_edge("user_input", "chat")
    workflow.add_conditional_edges("chat", tool_route)
    workflow.add_conditional_edges("tool_node", tool_result_route)

    graph = workflow.compile(store=store, checkpointer=checkpointer)
    return graph
