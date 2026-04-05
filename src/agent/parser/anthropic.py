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
    CompletionResponseDelta,
    CompletionResponseToolCall,
    ConversationMessage,
    HistoryMessage,
    ToolArgument,
)

class AnthropicEventParser:
    def __init__(self):
        self.tool_calls:dict[str,list[tuple[str,str]]] = {}
    
    def decode_message_tools(self, message: AnyMessage):
        if isinstance(message, AIMessage):
            for tool_call in message.tool_calls:
                if tool_call['id'] and tool_call['id'] not in self.tool_calls:
                    self.tool_calls[tool_call['id']] = []
                    for arg in tool_call['args'].items():
                        print(f"Decoded tool argument: {arg}")
                        self.tool_calls[tool_call['id']].append(arg)
                        
    def decode_history(self, messages: list[AnyMessage]):
        """
        Extract necessary information from the message history
        """
        for message in messages:
            self.decode_message_tools(message)
    
    def parse_message(self, message: AnyMessage) -> HistoryMessage:
        if isinstance(message, HumanMessage):
            return ConversationMessage(
                role="user",
                content=message.content,
                attachments=[], # TODO
                thought="",
            )
        elif isinstance(message, AIMessage):
            thought = ""
            content = message.content
            
            if message.response_metadata['model_provider'] == 'anthropic':
                # anthropic uses a chunked response format
                print(message.content)
                thought = ""
                content = ""
                for chunk in message.content:
                    thought += chunk.get("thinking", "")
                    content += chunk.get("text", "")
            return ConversationMessage(
                role="assistant",
                content=content,
                attachments=[], # TODO
                thought=thought,
            )
        raise ValueError(f"Unsupported message type: {type(message)}")
    
    def parse_event(self, event: StreamPart, message_id: str) -> list[CompletionResponseDelta]:
        deltas = []
        if event['type'] == 'messages':
            chunk, meta = event['data']
            if isinstance(chunk, AIMessage):
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
            elif isinstance(chunk, ToolMessage):
                deltas.append(CompletionResponseToolCall(
                    tool_name=chunk.name,
                    status="approved",
                    tool_response=chunk.content,
                    message_id=message_id,
                    tool_arguments=[
                        ToolArgument(
                            argument_name=arg_name,
                            argument=arg_value
                        )
                        for arg_name, arg_value in self.tool_calls.get(chunk.tool_call_id, [])
                    ]
                ))
                
        return deltas