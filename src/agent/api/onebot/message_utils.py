import re

from agent.api.conversation_models import CompletionResponseToolCall

_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")

TOOL_FORWARD_THRESHOLD = 200
TOOL_TRUNCATE_THRESHOLD = 8000
_TOOL_FIELD_HEAD_LIMIT = 2000


def extract_paragraphs(text: str, flush: bool = False) -> tuple[list[str], str]:
    normalized = text.replace("\r\n", "\n")
    parts = _PARAGRAPH_SPLIT_RE.split(normalized)
    if len(parts) == 1:
        if flush:
            stripped = normalized.strip()
            return ([stripped] if stripped else []), ""
        return [], normalized

    if flush:
        paragraphs = [part.strip() for part in parts if part.strip()]
        return paragraphs, ""

    paragraphs = [part.strip() for part in parts[:-1] if part.strip()]
    remainder = parts[-1]
    return paragraphs, remainder


def trim_head(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}\n...(truncated)"


def format_tool_paragraph(tool_call: CompletionResponseToolCall, trim_long_fields: bool = False) -> str:
    lines = [f"Tool: {tool_call.tool_name}"]

    if tool_call.tool_arguments:
        arguments = "; ".join(
            f"{argument.argument_name}={argument.argument}"
            for argument in tool_call.tool_arguments
        )
        if trim_long_fields:
            arguments = trim_head(arguments, _TOOL_FIELD_HEAD_LIMIT)
        lines.append(f"Arguments: {arguments}")

    if tool_call.status == "pending":
        lines.append("Status: pending")
        if tool_call.pending_reason.strip():
            lines.append(tool_call.pending_reason.strip())
        return "\n".join(lines)

    if tool_call.status == "rejected":
        lines.append("Status: rejected")
        if tool_call.pending_reason.strip():
            lines.append(tool_call.pending_reason.strip())
        return "\n".join(lines)

    if tool_call.tool_response.strip():
        tool_response = tool_call.tool_response.strip()
        if trim_long_fields:
            tool_response = trim_head(tool_response, _TOOL_FIELD_HEAD_LIMIT)
        lines.append("Status: completed")
        lines.append(tool_response)
        return "\n".join(lines)

    lines.append("Status: running")
    return "\n".join(lines)

