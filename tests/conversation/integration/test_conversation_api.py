from __future__ import annotations

import uuid
import datetime as dt

import pytest
from fastapi.testclient import TestClient

from agent.api.conversation import router as conversation_router
from agent.api.conversation_models import CompletionResponseDelta
from agent.api.conversation_service import delete_conversation as delete_conversation_record
from agent.db.models import Attachment, Conversation, Message, MessageAttachment


pytestmark = pytest.mark.integration


class FakeCheckpointer:
    def __init__(self):
        self.deleted_threads: list[str] = []

    async def adelete_thread(self, conversation_id: str):
        self.deleted_threads.append(conversation_id)


class FakeGraph:
    def __init__(self):
        self.checkpointer = FakeCheckpointer()


class FakeConversationRunner:
    def __init__(self, session_factory, graph):
        self.session_factory = session_factory
        self.graph = graph
        self.running: set[str] = set()
        self.cancelled: list[str] = []
        self.run_calls: list[dict] = []

    def is_running(self, conversation_id: str) -> bool:
        return conversation_id in self.running

    async def cancel(self, conversation_id: str):
        self.cancelled.append(conversation_id)
        self.running.discard(conversation_id)

    async def run(self, conversation_id, content, restart_message_id=None, attachments=None):
        self.run_calls.append(
            {
                "conversation_id": conversation_id,
                "content": content,
                "restart_message_id": restart_message_id,
                "attachments": attachments or [],
            }
        )
        return {"job": "fake"}

    async def stream(self, conversation_id, need_history, job):
        yield CompletionResponseDelta(
            message_id="message-1",
            delta=f"reply:{conversation_id}:{need_history}:{job['job']}",
            is_thinking=False,
        )

    async def delete_conversation(self, conversation_id):
        self.running.discard(conversation_id)
        return await delete_conversation_record(self.session_factory, self.graph, conversation_id)


def test_conversation_crud_search_cancel_and_completion_stream(
    app_factory,
    sqlite_session_factory,
    run_async,
):
    graph = FakeGraph()
    runner = FakeConversationRunner(sqlite_session_factory, graph)
    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.state.ConversationRunner = runner
    app.state.graph = graph
    app.include_router(conversation_router, prefix="/api")
    client = TestClient(app)

    created = client.post("/api/conversation")
    conversation_id = created.json()["conversation_id"]
    runner.running.add(conversation_id)

    patched = client.patch(
        f"/api/conversation/{conversation_id}",
        json={"title": "Pinned Project Chat", "is_pinned": True},
    )

    async def _seed_message():
        async with sqlite_session_factory() as session:
            session.add(
                Message(
                    id=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    seq=1,
                    content="The sprint review has API testing notes.",
                )
            )
            await session.commit()

    run_async(_seed_message())

    listed = client.get("/api/conversations/")
    searched = client.get("/api/conversations/search", params={"keywords": "sprint API"})
    bad_search = client.get("/api/conversations/search", params={"keywords": " "})
    cancelled = client.post(
        "/api/conversation/cancelchat",
        params={"conversation_id": conversation_id},
    )
    not_running = client.post(
        "/api/conversation/cancelchat",
        params={"conversation_id": conversation_id},
    )
    with client.stream(
        "POST",
        "/api/conversation/completion",
        json={
            "conversation_id": conversation_id,
            "request_id": str(uuid.uuid4()),
            "content": "hello",
            "created_at": 1,
            "attachments": [],
            "need_history": False,
        },
    ) as stream:
        stream_text = stream.read().decode("utf-8")

    deleted = client.delete(f"/api/conversation/{conversation_id}")
    missing = client.delete(f"/api/conversation/{conversation_id}")

    assert created.status_code == 200
    assert patched.status_code == 200
    assert listed.status_code == 200
    assert listed.json()["conversations"][0]["title"] == "Pinned Project Chat"
    assert listed.json()["conversations"][0]["is_active"] is True
    assert searched.status_code == 200
    assert searched.json()["conversations"][0]["conversation_id"] == conversation_id
    assert bad_search.status_code == 400
    assert cancelled.status_code == 200
    assert cancelled.json() == {"status": "cancelled"}
    assert not_running.status_code == 400
    assert "event: delta" in stream_text
    assert "reply:" in stream_text
    assert runner.run_calls[0]["content"] == "hello"
    assert deleted.status_code == 200
    assert graph.checkpointer.deleted_threads == [conversation_id]
    assert missing.status_code == 404


def test_completion_stream_uses_restart_message_and_pending_attachment(
    app_factory,
    sqlite_session_factory,
    run_async,
):
    graph = FakeGraph()
    runner = FakeConversationRunner(sqlite_session_factory, graph)
    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.state.ConversationRunner = runner
    app.state.graph = graph
    app.include_router(conversation_router, prefix="/api")
    client = TestClient(app)

    conversation_id = client.post("/api/conversation").json()["conversation_id"]
    restart_message_id = str(uuid.uuid4())
    attachment_id = str(uuid.uuid4())
    stored_attachment_id = str(uuid.uuid4())

    async def _seed_context():
        async with sqlite_session_factory() as session:
            session.add(
                Message(
                    id=restart_message_id,
                    conversation_id=conversation_id,
                    seq=1,
                    content="restart here",
                )
            )
            session.add(
                Attachment(
                    id=stored_attachment_id,
                    hash="a" * 64,
                    path="/tmp/opencrab-test.txt",
                    status="completed",
                )
            )
            session.add(
                MessageAttachment(
                    id=attachment_id,
                    message_id=None,
                    attachment_id=stored_attachment_id,
                    name="opencrab-test.txt",
                )
            )
            await session.commit()

    run_async(_seed_context())

    with client.stream(
        "POST",
        "/api/conversation/completion",
        json={
            "conversation_id": conversation_id,
            "request_id": str(uuid.uuid4()),
            "content": None,
            "created_at": 1,
            "attachments": [attachment_id],
            "need_history": True,
            "restart_message_id": restart_message_id,
        },
    ) as stream:
        stream_text = stream.read().decode("utf-8")

    assert stream.status_code == 200
    assert "event: delta" in stream_text
    assert runner.run_calls == [
        {
            "conversation_id": conversation_id,
            "content": "",
            "restart_message_id": restart_message_id,
            "attachments": [attachment_id],
        }
    ]


def test_completion_delegates_restart_message_and_attachment_refs_to_runner(
    app_factory,
    sqlite_session_factory,
    run_async,
):
    graph = FakeGraph()
    runner = FakeConversationRunner(sqlite_session_factory, graph)
    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.state.ConversationRunner = runner
    app.state.graph = graph
    app.include_router(conversation_router, prefix="/api")
    client = TestClient(app)

    conversation_id = client.post("/api/conversation").json()["conversation_id"]
    other_conversation_id = client.post("/api/conversation").json()["conversation_id"]
    other_message_id = str(uuid.uuid4())

    async def _seed_other_message():
        async with sqlite_session_factory() as session:
            session.add(
                Message(
                    id=other_message_id,
                    conversation_id=other_conversation_id,
                    seq=1,
                    content="belongs elsewhere",
                )
            )
            await session.commit()

    run_async(_seed_other_message())

    wrong_restart = client.post(
        "/api/conversation/completion",
        json={
            "conversation_id": conversation_id,
            "request_id": str(uuid.uuid4()),
            "content": "hello",
            "created_at": 1,
            "attachments": [],
            "need_history": False,
            "restart_message_id": other_message_id,
        },
    )
    missing_attachment_id = str(uuid.uuid4())
    missing_attachment = client.post(
        "/api/conversation/completion",
        json={
            "conversation_id": conversation_id,
            "request_id": str(uuid.uuid4()),
            "content": None,
            "created_at": 1,
            "attachments": [missing_attachment_id],
            "need_history": False,
        },
    )

    assert wrong_restart.status_code == 200
    assert missing_attachment.status_code == 200
    assert runner.run_calls == [
        {
            "conversation_id": conversation_id,
            "content": "hello",
            "restart_message_id": other_message_id,
            "attachments": [],
        },
        {
            "conversation_id": conversation_id,
            "content": "",
            "restart_message_id": None,
            "attachments": [missing_attachment_id],
        },
    ]


def test_list_orders_pinned_then_recent_and_marks_active_conversation(
    app_factory,
    sqlite_session_factory,
    run_async,
):
    graph = FakeGraph()
    runner = FakeConversationRunner(sqlite_session_factory, graph)
    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.state.ConversationRunner = runner
    app.state.graph = graph
    app.include_router(conversation_router, prefix="/api")
    client = TestClient(app)

    older_pinned_id = str(uuid.uuid4())
    newer_unpinned_id = str(uuid.uuid4())
    newest_pinned_id = str(uuid.uuid4())

    async def _seed_conversations():
        async with sqlite_session_factory() as session:
            session.add_all(
                [
                    Conversation(
                        id=older_pinned_id,
                        title="Older Pinned",
                        pinned=True,
                        time_last_used=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
                    ),
                    Conversation(
                        id=newer_unpinned_id,
                        title="Newer Unpinned",
                        pinned=False,
                        time_last_used=dt.datetime(2026, 1, 3, tzinfo=dt.timezone.utc),
                    ),
                    Conversation(
                        id=newest_pinned_id,
                        title="Newest Pinned",
                        pinned=True,
                        time_last_used=dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc),
                    ),
                ]
            )
            await session.commit()

    run_async(_seed_conversations())
    runner.running.add(older_pinned_id)

    response = client.get("/api/conversations/", params={"page": 1, "page_size": 2})

    assert response.status_code == 200
    conversations = response.json()["conversations"]
    assert [item["conversation_id"] for item in conversations] == [newest_pinned_id, older_pinned_id]
    assert conversations[1]["is_active"] is True
