from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    ToolMessage,
    AnyMessage,
)

from langgraph.types import StreamPart
import json
from agent.api.conversation_models import (
    CompletionResponseDelta,
    CompletionResponseToolCall,
    ConversationMessage,
    HistoryMessage,
    ToolMessage as HistoryToolMessage,
    ToolArgument,
)
from typing import Literal

class AnthropicEventParser:
    def _stringify_content(self, content: object) -> str:
        if isinstance(content, str):
            return content
        return json.dumps(content, default=str)

    def _extract_ai_text_and_thought(self, message: AIMessage) -> tuple[str, str]:
        thought = ""
        content = ""

        if isinstance(message.content, str):
            return message.content, thought

        if not isinstance(message.content, list):
            return str(message.content), thought

        is_anthropic = str(message.response_metadata.get("model_provider", "")) == "anthropic"
        for chunk in message.content:
            if isinstance(chunk, str):
                content += chunk
                continue
            if not isinstance(chunk, dict):
                continue
            if is_anthropic:
                thought += str(chunk.get("thinking", ""))
            content += str(chunk.get("text", ""))

        return content, thought

    def _resolve_tool_arguments(self, message: ToolMessage) -> list[ToolArgument]:
        resolved_args: list[tuple[str, str]] = []
        raw_args = message.additional_kwargs.get("args", [])
        if isinstance(raw_args, list):
            for item in raw_args:
                if not isinstance(item, dict):
                    continue
                for arg_name, arg_value in item.items():
                    resolved_args.append((str(arg_name), str(arg_value)))

        return [
            ToolArgument(argument_name=arg_name, argument=arg_value)
            for arg_name, arg_value in resolved_args
        ]

    def _resolve_hitl_status(self, message: ToolMessage) -> tuple[Literal["approved", "rejected", "pending"], str]:
        hitl_status = message.additional_kwargs.get("hitl_status", {})
        if not isinstance(hitl_status, dict):
            return "approved", ""

        status = str(hitl_status.get("status", "approved")).lower()
        pending_reason = str(hitl_status.get("pending_reason", ""))
        if status == "pending":
            return "pending", pending_reason
        if status == "rejected":
            return "rejected", pending_reason
        return "approved", pending_reason
    
    def parse_message(self, message: AnyMessage, attachments: list[str] | None = None) -> HistoryMessage:
        """
        Parse a complete message into a HistoryMessage
        """
        normalized_attachments = attachments or []

        if isinstance(message, HumanMessage):
            return ConversationMessage(
                role="user",
                content=self._stringify_content(message.content),
                attachments=normalized_attachments,
                thought="",
            )
        elif isinstance(message, AIMessage):
            content, thought = self._extract_ai_text_and_thought(message)
            return ConversationMessage(
                role="assistant",
                content=content,
                attachments=normalized_attachments,
                thought=thought,
            )
        elif isinstance(message, ToolMessage):
            status, pending_reason = self._resolve_hitl_status(message)
            tool_response = self._stringify_content(message.content)
            return HistoryToolMessage(
                tool_name=message.name or "",
                status=status,
                pending_reason=pending_reason,
                tool_response=tool_response,
                tool_arguments=self._resolve_tool_arguments(message),
            )
        raise ValueError(f"Unsupported message type: {type(message)}")
    
    def parse_message_delta(self, chunk: AnyMessage, message_id: str) -> list[CompletionResponseDelta]:
        """
        Parse a message chunk into a list of CompletionResponseDelta objects
        """
        deltas = []
        if isinstance(chunk, AIMessage):
            content, thought = self._extract_ai_text_and_thought(chunk)

            if thought:
                deltas.append(CompletionResponseDelta(
                    message_id=message_id,
                    delta=thought,
                    is_thinking=True,
                ))
            if content:
                deltas.append(CompletionResponseDelta(
                    message_id=message_id,
                    delta=content,
                    is_thinking=False,
                ))
        elif isinstance(chunk, ToolMessage):
            status, pending_reason = self._resolve_hitl_status(chunk)
            tool_response = self._stringify_content(chunk.content)
            deltas.append(CompletionResponseToolCall(
                tool_name=chunk.name or "",
                status=status,
                pending_reason=pending_reason,
                tool_response=tool_response,
                message_id=message_id,
                tool_arguments=self._resolve_tool_arguments(chunk),
            ))
        return deltas
                
    def parse_event(self, event: StreamPart, message_id: str) -> list[CompletionResponseDelta]:
        deltas = []
        if event['type'] == 'messages':
            chunk, _meta = event['data']
            deltas.extend(self.parse_message_delta(chunk, message_id))
                
        return deltas
