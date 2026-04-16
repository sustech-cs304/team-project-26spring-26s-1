from __future__ import annotations

import json
from typing import Any

from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import RemoveMessage
from langchain_openai import ChatOpenAI
from langchain_qwq import ChatQwen
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime

from agent.config import LLMEndpointConfig, get_config, jinja_env
from agent.core.state import AgentState
from agent.tools.core_memory import core_memory_get

CHARS_PER_TOKEN = 4
COMPACTION_METADATA_KEY = "context_compaction"
COMPACTION_PROMPT = """Provide a detailed prompt for continuing our conversation above.
Focus on information that would be helpful for continuing the conversation, including what we did, what we're doing, which files we're working on, and what we're going to do next.
The summary that you construct will be used so that another agent can read it and continue the work.
Do not call any tools. Respond only with the summary text.
Respond in the same language as the user's messages in the conversation.

When constructing the summary, try to stick to this template:
---
## Goal

[What goal(s) is the user trying to accomplish?]

## Instructions

- [What important instructions did the user give you that are relevant]
- [If there is a plan or spec, include information about it so next agent can continue using it]

## Discoveries

[What notable things were learned during this conversation that would be useful for the next agent to know when continuing the work]

## Accomplished

[What work has been completed, what work is still in progress, and what work is left?]

## Relevant files / directories

[Construct a structured list of relevant files that have been read, edited, or created that pertain to the task at hand. If all the files in a directory are relevant, include the path to the directory.]
---"""


def _build_model(endpoint: LLMEndpointConfig):
    if endpoint.type == "OpenAI":
        return ChatOpenAI(
            model=endpoint.model,
            api_key=endpoint.api_key,
            base_url=endpoint.base_url,
        )
    if endpoint.type == "Qwen":
        return ChatQwen(
            model=endpoint.model,
            api_key=endpoint.api_key,
            base_url=endpoint.base_url,
        )
    if endpoint.type == "Anthropic":
        return ChatAnthropic(
            model=endpoint.model,
            api_key=endpoint.api_key,
            base_url=endpoint.base_url,
        )
    raise ValueError(f"Model type {endpoint.type} not supported")


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for chunk in content:
            if isinstance(chunk, str):
                parts.append(chunk)
                continue
            if isinstance(chunk, dict):
                text = chunk.get("text")
                if text:
                    parts.append(str(text))
                    continue
                parts.append(json.dumps(chunk, ensure_ascii=False, default=str))
                continue
            parts.append(str(chunk))
        return "".join(parts)
    return json.dumps(content, ensure_ascii=False, default=str)


def _extract_text(message: AIMessage) -> str:
    return _stringify_content(message.content).strip()


def _estimate_tokens(text: str) -> int:
    return max(0, round(len(text) / CHARS_PER_TOKEN))


def _serialize_message(message: Any) -> str:
    role = "message"
    if isinstance(message, SystemMessage):
        role = "system"
    elif isinstance(message, HumanMessage):
        role = "user"
    elif isinstance(message, AIMessage):
        role = "assistant"
    elif isinstance(message, ToolMessage):
        role = f"tool:{message.name or ''}"

    sections = [role, _stringify_content(getattr(message, "content", ""))]
    if isinstance(message, AIMessage) and message.tool_calls:
        sections.append(json.dumps(message.tool_calls, ensure_ascii=False, default=str))
    if isinstance(message, ToolMessage):
        if message.tool_call_id:
            sections.append(f"tool_call_id={message.tool_call_id}")
        if message.additional_kwargs:
            sections.append(json.dumps(message.additional_kwargs, ensure_ascii=False, default=str))
    return "\n".join(section for section in sections if section)


def _estimate_message_tokens(messages: list[Any]) -> int:
    return sum(_estimate_tokens(_serialize_message(message)) for message in messages)


def _is_compaction_prompt(message: Any) -> bool:
    if not isinstance(message, HumanMessage):
        return False
    metadata = message.additional_kwargs.get(COMPACTION_METADATA_KEY, {})
    return bool(isinstance(metadata, dict) and metadata.get("kind") == "prompt")


async def _estimate_system_prompt_tokens(runtime: Runtime[Any], token_limit: int) -> int:
    store = runtime.store
    core_memory_entries: list[tuple[str, str]] = []
    if store:
        core_memory_entries = await core_memory_get(store)

    system_prompt = jinja_env.get_template("system_prompt.j2").render(
        core_memory=core_memory_entries,
        token_limit=token_limit,
    )
    return _estimate_tokens(system_prompt)


async def context_compacting_node(state: AgentState, runtime: Runtime[Any]) -> AgentState:
    messages = list(state.get("messages", []))
    if len(messages) < 2:
        return state

    endpoint = get_config().api.agent
    token_budget = endpoint.max_token_count
    if token_budget <= 0:
        return state

    estimated_total = _estimate_message_tokens(messages)
    estimated_total += await _estimate_system_prompt_tokens(runtime, token_budget)
    if estimated_total <= token_budget:
        return state

    last_human_index = -1
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            last_human_index = index
            break

    if last_human_index <= 0:
        return state

    prefix = [message for message in messages[:last_human_index] if not _is_compaction_prompt(message)]
    suffix = messages[last_human_index:]
    if not prefix:
        return state

    model = _build_model(endpoint)
    try:
        response = await model.ainvoke([
            *prefix,
            HumanMessage(content=COMPACTION_PROMPT),
        ])
    except Exception as exc:
        print(f"Failed to compact context: {exc}")
        return state

    if not isinstance(response, AIMessage):
        return state

    summary = _extract_text(response)
    if not summary:
        return state

    compacted_messages = [
        RemoveMessage(id=REMOVE_ALL_MESSAGES),
        HumanMessage(
            content="What did we do so far?",
            additional_kwargs={
                COMPACTION_METADATA_KEY: {
                    "kind": "prompt",
                }
            },
        ),
        AIMessage(
            content=summary,
            additional_kwargs={
                COMPACTION_METADATA_KEY: {
                    "kind": "summary",
                }
            },
        ),
        *suffix,
    ]
    return {"messages": compacted_messages}
