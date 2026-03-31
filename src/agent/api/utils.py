from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    BaseMessage,
    AnyMessage,
)
import agent.db.models as db_models
from pydantic import BaseModel, Field, TypeAdapter
from agent.api.models import (
    ConversationMessage,
    ToolArgument,
    ToolMessage,
    HistoryMessage,
)

def decode_message(message: db_models.Message) -> HistoryMessage:
    def _extract_text(content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    chunks.append(str(item.get("text", "")))
                else:
                    chunks.append(str(item))
            return "".join(chunks)
        return str(content or "")

    def _split_thought(raw: str) -> tuple[str, str]:
        open_tag = "<think>"
        close_tag = "</think>"
        open_at = raw.find(open_tag)
        close_at = raw.find(close_tag)
        if open_at == -1 or close_at == -1 or close_at < open_at:
            return "", raw
        thought = raw[open_at + len(open_tag):close_at].strip()
        content = (raw[:open_at] + raw[close_at + len(close_tag):]).strip()
        return thought, content

    # message_object = AnyMessage.model_validate_json(message.content)
    message_object = TypeAdapter(AnyMessage).validate_json(message.content)
    
    if isinstance(message_object, ToolMessage):
        #TODO: parse tool message properly instead of just putting the whole content in thought
        raise NotImplementedError("ToolMessage parsing not implemented yet")
    
    if isinstance(message_object, HumanMessage):
        role = "user"
    elif isinstance(message_object, AIMessage):
        role = "assistant"
    else:
        role = "system"
    raw_content = _extract_text(message_object.content)
    thought, content = _split_thought(raw_content)
    
    return ConversationMessage(
        role=role,
        content=content,
        attachments=[], #TODO: parse attachments properly instead of leaving it empty
        thought=thought
    )