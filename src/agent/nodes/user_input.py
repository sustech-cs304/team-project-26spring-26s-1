from langchain.messages import HumanMessage
from langgraph.types import interrupt

from agent.core.state import AgentState, ResumePayload


async def user_input_node(state: AgentState) -> AgentState:
    resume_payload: ResumePayload = interrupt({
        "type": "user_input",
        "message": "Awaiting user input",
    })
    if resume_payload["attachment_content"]:
        text = f"{resume_payload['user_input']}\n\nAttached content:\n{resume_payload['attachment_content']}"
    else:
        text = resume_payload["user_input"]
    return {
        "messages": [HumanMessage(role="user", content=str(text))],
    }
