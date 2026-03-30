import pydantic
from typing import Literal, Union
from typing import Dict, Any, List, ClassVar

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
class CompletionResponseHistory(pydantic.BaseModel):
    message_id: str
    type: str
    created_at: int
    finished_at: int
    data: AnyMessage    
    _event_type: ClassVar[str] = "history"
        
class CompletionResponseDelta(pydantic.BaseModel):
    message_id: str
    delta: str
    is_thinking: bool
    _event_type: ClassVar[str] = "delta"
    
class CompletionResponseMetadata(pydantic.BaseModel):
    title: str
    _event_type: ClassVar[str] = "meta_data"

class CompletionResponseToolCall(ToolMessage):
    message_id: str
    _event_type: ClassVar[str] = "tool_call"

class CompletionResponseError(pydantic.BaseModel):
    error_message: str
    _event_type: ClassVar[str] = "error"

class CompletionEventKeepAlive(pydantic.BaseModel):
    data : list = []
    _event_type: Literal["keep_alive"]= "keep_alive"

