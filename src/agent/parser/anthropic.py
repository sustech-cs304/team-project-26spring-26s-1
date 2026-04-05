from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    BaseMessage,
    AnyMessage,
)

from langgraph.types import StreamPart
import agent.db.models as db_models
import json
from pydantic import BaseModel, Field, TypeAdapter
from agent.api.models import (
    CompletionResponseDelta
)

class AnthropicEventParser:
    def __init__(self):
        pass
    
    def parse_event(self, event: StreamPart, message_id: str) -> [CompletionResponseDelta]:
        deltas = []
        if event['type'] == 'messages':
            chunk, meta = event['data']
            thought = ""
            content = ""
            
            for content_chunks in chunk.content:
                thought += content_chunks.get("thinking", "")
                content += content_chunks.get("text", "")

            if thinking := thought.strip():
                deltas.append(CompletionResponseDelta(
                    message_id=message_id,
                    delta=thinking,
                    is_thinking=True,
                ))
            if content.strip():
                deltas.append(CompletionResponseDelta(
                    message_id=message_id,
                    delta=content,
                    is_thinking=False,
                ))
        return deltas