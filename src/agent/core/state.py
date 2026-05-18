from typing import Annotated, TypedDict

from langgraph.graph.message import AnyMessage, add_messages

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

class ResumePayload(TypedDict):
    user_input: str
    attachment_content: str
