import pydantic
from typing import Literal, Union, ClassVar, Annotated
from pydantic import Field

class ConversationMessage(pydantic.BaseModel):
    type : Literal["message"] = "message"
    
    role: str
    content: str
    attachments: list[str] = []
    thought: str = ""
    
class ToolArgument(pydantic.BaseModel):
    argument_name: str
    argument: str
    
class ToolMessage(pydantic.BaseModel):
    type : Literal["tool"] = "tool"
    
    tool_name: str
    tool_arguments: list[ToolArgument] = []
    status: Literal["approved", "rejected", "pending"] = "pending"
    pending_reason: str = ""
    tool_response: str = ""

HistoryMessage = Annotated[Union[ConversationMessage, ToolMessage], Field(discriminator="type")]

class CompletionResponseHistory(pydantic.BaseModel):
    message_id: str
    created_at: int
    finished_at: int
    data: HistoryMessage
    _event_type: ClassVar[str] = "history"
        
class CompletionResponseDelta(pydantic.BaseModel):
    message_id: str
    delta: str
    is_thinking: bool
    _event_type: ClassVar[str] = "delta"
    
class CompletionResponseMetadata(pydantic.BaseModel):
    title: str
    _event_type: ClassVar[str] = "metadata"

class CompletionResponseToolCall(ToolMessage):
    message_id: str
    _event_type: ClassVar[str] = "tool_call"

class CompletionEventKeepAlive(pydantic.BaseModel):
    _event_type: Literal["keep_alive"]= "keep_alive"

class CompletionUserMessage(pydantic.BaseModel):
    message_id : str
    _event_type: ClassVar[str] = "user_message"
