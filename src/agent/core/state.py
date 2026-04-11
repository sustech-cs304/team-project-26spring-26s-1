from typing import Annotated, TypedDict
import operator
from langgraph.graph.message import AnyMessage

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]

class ResumePayload(TypedDict):
    user_input: str
    attachment_content: str
