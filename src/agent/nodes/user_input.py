from langchain.messages import HumanMessage
from langgraph.types import interrupt

from agent.core.state import AgentState


async def user_input_node(state: AgentState) -> AgentState:
    user_text = interrupt({
        "type": "user_input",
        "message": "Awaiting user input",
    })
    return {"messages": [HumanMessage(role="user", content=str(user_text))]}
