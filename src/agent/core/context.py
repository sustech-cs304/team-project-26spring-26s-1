from typing import Annotated, TypedDict
from agent.config import AppConfig
from langgraph.graph.message import AnyMessage

class AgentContext(TypedDict):
    config: AppConfig
