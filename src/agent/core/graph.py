from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END, START
from langchain.messages import AnyMessage, AIMessage
from langgraph.prebuilt.tool_node import ToolCallWithContext
from agent.config import AppConfig
from agent.nodes.model import Model
from agent.core.state import AgentState
from agent.core.context import AgentContext
from agent.tools import tools as agent_tools, tool_node
from langgraph.types import Send
from langgraph.store.base import BaseStore
from langgraph.checkpoint.base import BaseCheckpointSaver

async def create_graph(config: AppConfig, store : BaseStore, checkpointer: BaseCheckpointSaver):
    workflow = StateGraph(AgentState, context_schema=AgentContext)
    
    model = Model.get(
        name = config.api.agent.type,
        model = config.api.agent.model,
        api_key = config.api.agent.api_key,
        base_url = config.api.agent.base_url,
        tools = agent_tools
    )
    
    async def tool_route(state: AgentState):
        if not state["messages"]:
            return END
        last_message = state['messages'][-1]
        if not isinstance(last_message, AIMessage):
            return END
        tool_calls = last_message.tool_calls
        if not tool_calls:
            return END
        return [
            Send("tool_node", (
                ToolCallWithContext(
                    __type="tool_call_with_context",
                    tool_call=tool_call,
                    state=state
            )))
            for tool_call in tool_calls
        ]
    
    workflow.add_node("chat", model.invoke_node)
    workflow.add_node("tool_node", tool_node)
    workflow.add_edge(START, "chat")
    workflow.add_conditional_edges("chat", tool_route)
    workflow.add_edge("tool_node", "chat")

    graph = workflow.compile(store=store, checkpointer=checkpointer)
    return graph
    
    