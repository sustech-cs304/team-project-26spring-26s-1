from __future__ import annotations

import json
import time
from uuid import uuid4
from dataclasses import dataclass
from typing import Any

from agent.api.models import (
	CompletionResponseDelta,
	CompletionResponseError,
	CompletionResponseHistory,
	CompletionResponseToolCall,
	ConversationMessage,
	ToolArgument,
)


@dataclass
class _StreamParseState:
	in_thinking: bool = False
	pending: str = ""


class MinimaxEventParser:
	"""Parse LangGraph stream events into API response model instances."""

	_THINK_OPEN = "<think>"
	_THINK_CLOSE = "</think>"

	def __init__(self) -> None:
		self._state = _StreamParseState()

	def parse_event(self, event: dict[str, Any]) -> list[Any]:
		"""Convert one LangGraph event dict into zero or more API model objects."""
		event_type = event.get("type")
		if event_type == "messages":
			return self._parse_messages_event(event)
		if event_type == "values":
			return self._parse_values_event(event)
		if event_type == "error":
			return [CompletionResponseError(error_message=str(event.get("data", "unknown error")))]
		return []

	def _parse_messages_event(self, event: dict[str, Any]) -> list[Any]:
		data = event.get("data")
		if not isinstance(data, (tuple, list)) or len(data) < 1:
			return []

		chunk = data[0]
		message_id = self._extract_message_id(chunk)
		outputs: list[Any] = []

		text = self._extract_content(chunk)
		if text:
			for is_thinking, delta in self._consume_stream_text(text):
				if not delta:
					continue
				outputs.append(
					CompletionResponseDelta(
						message_id=message_id,
						delta=delta,
						is_thinking=is_thinking,
					)
				)

		for tool in self._extract_tool_calls(chunk):
			outputs.append(
				CompletionResponseToolCall(
					message_id=message_id,
					tool_name=tool.get("name", "unknown_tool"),
					tool_arguments=self._convert_tool_args(tool.get("args", {})),
					status="pending",
					pending_reason="waiting for tool execution",
					tool_response="",
				)
			)

		return outputs

	def _parse_values_event(self, event: dict[str, Any]) -> list[Any]:
		data = event.get("data", {})
		messages = data.get("messages", []) if isinstance(data, dict) else []
		if not isinstance(messages, list):
			return []

		now = int(time.time())
		outputs: list[Any] = []

		for message in messages:
			role = self._extract_role(message)
			if role not in {"assistant", "ai", "user", "human", "system"}:
				continue

			raw_content = self._extract_content(message)
			thought, content = self._split_thought_and_content(raw_content)

			outputs.append(
				CompletionResponseHistory(
					message_id=self._extract_message_id(message),
					type="message",
					created_at=now,
					finished_at=now,
					data=ConversationMessage(
						role=self._normalize_role(role),
						content=content,
						attachments=[],
						thought=thought,
					),
				)
			)
		return outputs

	def _consume_stream_text(self, text: str) -> list[tuple[bool, str]]:
		merged = self._state.pending + text
		self._state.pending = ""
		return self._split_stream_text(merged)

	def _split_stream_text(self, text: str) -> list[tuple[bool, str]]:
		i = 0
		outputs: list[tuple[bool, str]] = []

		while i < len(text):
			if self._state.in_thinking:
				close_at = text.find(self._THINK_CLOSE, i)
				if close_at == -1:
					emit_end = self._emit_end_for_partial_tag(text, i, self._THINK_CLOSE)
					delta = text[i:emit_end]
					if delta:
						outputs.append((True, delta))
					self._state.pending = text[emit_end:]
					break

				delta = text[i:close_at]
				if delta:
					outputs.append((True, delta))
				self._state.in_thinking = False
				i = close_at + len(self._THINK_CLOSE)
				continue

			open_at = text.find(self._THINK_OPEN, i)
			if open_at == -1:
				emit_end = self._emit_end_for_partial_tag(text, i, self._THINK_OPEN)
				delta = text[i:emit_end]
				if delta:
					outputs.append((False, delta))
				self._state.pending = text[emit_end:]
				break

			delta = text[i:open_at]
			if delta:
				outputs.append((False, delta))
			self._state.in_thinking = True
			i = open_at + len(self._THINK_OPEN)

		return outputs

	@staticmethod
	def _emit_end_for_partial_tag(text: str, start: int, tag: str) -> int:
		tail = text[start:]
		max_len = min(len(tag) - 1, len(tail))
		keep = 0
		for size in range(max_len, 0, -1):
			if tail.endswith(tag[:size]):
				keep = size
				break
		return len(text) - keep

	@classmethod
	def _split_thought_and_content(cls, raw: str) -> tuple[str, str]:
		if not raw:
			return "", ""

		open_at = raw.find(cls._THINK_OPEN)
		close_at = raw.find(cls._THINK_CLOSE)
		if open_at == -1 or close_at == -1 or close_at < open_at:
			return "", raw

		thought = raw[open_at + len(cls._THINK_OPEN):close_at].strip()
		content = (raw[:open_at] + raw[close_at + len(cls._THINK_CLOSE):]).strip()
		return thought, content

	@staticmethod
	def _extract_content(message: Any) -> str:
		content = getattr(message, "content", "")
		if isinstance(content, list):
			# Some providers may return segmented content blocks.
			return "".join(str(item) for item in content)
		return str(content or "")

	@staticmethod
	def _extract_message_id(message: Any) -> str:
		message_id = getattr(message, "id", None)
		if message_id:
			return str(message_id)
		return str(uuid4())

	@staticmethod
	def _extract_role(message: Any) -> str:
		role = getattr(message, "role", None)
		if role:
			return str(role).lower()
		msg_type = getattr(message, "type", None)
		if msg_type:
			return str(msg_type).lower()
		class_name = message.__class__.__name__.lower()
		if "human" in class_name:
			return "user"
		if "ai" in class_name:
			return "assistant"
		return "assistant"

	@staticmethod
	def _normalize_role(role: str) -> str:
		if role in {"ai", "assistant"}:
			return "assistant"
		if role in {"human", "user"}:
			return "user"
		return role

	@staticmethod
	def _extract_tool_calls(message: Any) -> list[dict[str, Any]]:
		tool_calls = getattr(message, "tool_calls", []) or []
		normalized: list[dict[str, Any]] = []
		for tool in tool_calls:
			if isinstance(tool, dict):
				normalized.append(tool)
				continue
			normalized.append(
				{
					"name": getattr(tool, "name", "unknown_tool"),
					"args": getattr(tool, "args", {}),
				}
			)
		return normalized

	@staticmethod
	def _convert_tool_args(args: Any) -> list[ToolArgument]:
		if isinstance(args, dict):
			return [
				ToolArgument(argument_name=str(key), argument=MinimaxEventParser._stringify_arg(value))
				for key, value in args.items()
			]
		if isinstance(args, list):
			return [
				ToolArgument(argument_name=str(index), argument=MinimaxEventParser._stringify_arg(value))
				for index, value in enumerate(args)
			]
		if args is None:
			return []
		return [ToolArgument(argument_name="value", argument=MinimaxEventParser._stringify_arg(args))]

	@staticmethod
	def _stringify_arg(value: Any) -> str:
		if isinstance(value, str):
			return value
		try:
			return json.dumps(value, ensure_ascii=False)
		except TypeError:
			return str(value)


def parse_minimax_event(event: dict[str, Any], parser: MinimaxEventParser | None = None) -> list[Any]:
	"""Functional helper: parse one event with a provided or temporary parser."""
	event_parser = parser or MinimaxEventParser()
	return event_parser.parse_event(event)

