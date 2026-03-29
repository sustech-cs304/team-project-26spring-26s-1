import pydantic
from typing import Literal, Union

class ConversationMessage(pydantic.BaseModel):
    role: str
    content: str
    attachments: list[str] = []
    thought: str = ""
    
class ToolArgument(pydantic.BaseModel):
    argument_name: str
    argument: str
    
class ToolMessage(pydantic.BaseModel):
    tool_name: str
    tool_arguments: list[ToolArgument] = []
    status: Literal["approved", "rejected", "pending"] = "pending"
    pending_reason: str = ""
    tool_response: str = ""
    
AnyMessage = Union[ConversationMessage, ToolMessage]
