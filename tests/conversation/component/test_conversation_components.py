from __future__ import annotations

import asyncio
import datetime as dt
import uuid

import pytest
from langchain.messages import AIMessage, HumanMessage, ToolMessage

from agent.api.conversation_models import CompletionResponseDelta
from agent.api.conversation_runner import ConversationRunner, _ConversationJobState
from agent.db.models import Attachment, Conversation, Message, MessageAttachment
from agent.parser.anthropic import AnthropicEventParser


pytestmark = pytest.mark.component


def test_anthropic_parser_converts_history_messages_and_tool_delta():
    parser = AnthropicEventParser()
    tool_call_id = "tool-call-1"

    user = parser.parse_message(HumanMessage(content="hello"), attachments=["file-1"])
    assistant = parser.parse_message(
        AIMessage(
            content=[{"thinking": "think", "text": "answer"}],
            response_metadata={"model_provider": "anthropic"},
        )
    )
    tool = parser.parse_message(
        ToolMessage(
            content={"ok": True},
            name="calendar.create",
            tool_call_id=tool_call_id,
            additional_kwargs={
                "args": [{"title": "Review"}, {"duration": 30}],
                "hitl_status": {"status": "pending", "pending_reason": "needs approval"},
            },
        )
    )
    deltas = parser.parse_message_delta(
        AIMessage(
            content=[{"thinking": "plan", "text": "done"}],
            response_metadata={"model_provider": "anthropic"},
        ),
        message_id="message-1",
    )
    tool_delta = parser.parse_message_delta(
        ToolMessage(
            content="created",
            name="calendar.create",
            tool_call_id=tool_call_id,
            additional_kwargs={"args": [{"title": "Review"}]},
        ),
        message_id="tool-message-1",
    )

    assert user.role == "user"
    assert user.content == "hello"
    assert user.attachments == ["file-1"]
    assert assistant.role == "assistant"
    assert assistant.thought == "think"
    assert assistant.content == "answer"
    assert tool.tool_name == "calendar.create"
    assert tool.status == "pending"
    assert tool.pending_reason == "needs approval"
    assert [(item.argument_name, item.argument) for item in tool.tool_arguments] == [
        ("title", "Review"),
        ("duration", "30"),
    ]
    assert [(item.delta, item.is_thinking) for item in deltas] == [("plan", True), ("done", False)]
    assert tool_delta[0]._event_type == "tool_call"
    assert tool_delta[0].tool_response == "created"


def test_runner_stream_returns_persisted_history_without_active_job(
    sqlite_session_factory,
    run_async,
):
    conversation_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    attachment_id = str(uuid.uuid4())
    message_attachment_id = str(uuid.uuid4())

    async def _seed():
        async with sqlite_session_factory() as session:
            session.add(Conversation(id=conversation_id, title="History Chat"))
            session.add(
                Message(
                    id=message_id,
                    conversation_id=conversation_id,
                    created_at=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
                    finished_at=dt.datetime(2026, 1, 1, 0, 0, 1, tzinfo=dt.timezone.utc),
                    seq=1,
                    content=HumanMessage(content="remember this").model_dump_json(),
                )
            )
            session.add(Attachment(id=attachment_id, hash="b" * 64, path="/tmp/history.txt"))
            session.add(
                MessageAttachment(
                    id=message_attachment_id,
                    message_id=message_id,
                    attachment_id=attachment_id,
                    name="history.txt",
                )
            )
            await session.commit()

    async def _collect():
        runner = ConversationRunner(graph=object(), session_factory=sqlite_session_factory)
        return [event async for event in runner.stream(conversation_id, need_history=True)]

    run_async(_seed())
    events = run_async(_collect())

    assert len(events) == 1
    assert events[0]._event_type == "history"
    assert events[0].message_id == message_id
    assert events[0].data.role == "user"
    assert events[0].data.content == "remember this"
    assert events[0].data.attachments == [attachment_id]


def test_runner_stream_yields_user_message_history_then_live_delta(
    sqlite_session_factory,
    run_async,
):
    conversation_id = str(uuid.uuid4())
    stored_message_id = str(uuid.uuid4())
    live_message_id = str(uuid.uuid4())
    user_message_id = str(uuid.uuid4())

    async def _seed():
        async with sqlite_session_factory() as session:
            session.add(Conversation(id=conversation_id, title="Live Chat"))
            session.add(
                Message(
                    id=stored_message_id,
                    conversation_id=conversation_id,
                    created_at=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
                    seq=1,
                    content=HumanMessage(content="previous").model_dump_json(),
                )
            )
            await session.commit()

    async def _collect():
        runner = ConversationRunner(graph=object(), session_factory=sqlite_session_factory)
        job = _ConversationJobState()
        job.user_message_id = user_message_id
        job.history = [
            CompletionResponseDelta(message_id=live_message_id, delta="streamed", is_thinking=False)
        ]
        job.task = asyncio.create_task(asyncio.sleep(0))
        await job.task
        return [event async for event in runner.stream(conversation_id, need_history=True, job=job)]

    run_async(_seed())
    events = run_async(_collect())

    assert [event._event_type for event in events] == ["user_message", "history", "delta"]
    assert events[0].message_id == user_message_id
    assert events[1].message_id == stored_message_id
    assert events[2].message_id == live_message_id
    assert events[2].delta == "streamed"
