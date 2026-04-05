from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    BaseMessage,
    AnyMessage,
)
import agent.db.models as db_models
import json
from pydantic import BaseModel, Field, TypeAdapter
from agent.api.models import (
    ConversationMessage,
    ToolArgument,
    ToolMessage,
    HistoryMessage,
)

def decode_message(message: db_models.Message) -> HistoryMessage:
    message_data: AnyMessage = TypeAdapter(AnyMessage).validate_json(message.content)
    if isinstance(message_data, HumanMessage):
        return ConversationMessage(
            role="user",
            content=message_data.content,
            attachments=[], # TODO
            thought="",
        )
    elif isinstance(message_data, AIMessage):
        thought = ""
        content = message_data.content
        
        if message_data.response_metadata['model_provider'] == 'anthropic':
            # anthropic uses a chunked response format
            print(message_data.content)
            thought = ""
            content = ""
            for chunk in message_data.content:
                thought += chunk.get("thinking", "")
                content += chunk.get("text", "")
        return ConversationMessage(
            role="assistant",
            content=content,
            attachments=[], # TODO
            thought=thought,
        )