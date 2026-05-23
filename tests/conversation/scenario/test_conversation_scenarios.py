from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from agent.api.conversation import router as conversation_router
from agent.api.conversation_models import CompletionResponseDelta
from agent.api.conversation_service import delete_conversation as delete_conversation_record
from agent.db.models import Attachment, Message, MessageAttachment


pytestmark = pytest.mark.scenario


class ScenarioCheckpointer:
    def __init__(self):
        self.deleted_threads: list[str] = []

    async def adelete_thread(self, conversation_id: str):
        self.deleted_threads.append(conversation_id)


class ScenarioGraph:
    def __init__(self):
        self.checkpointer = ScenarioCheckpointer()


class ScenarioRunner:
    def __init__(self, session_factory, graph):
        self.session_factory = session_factory
        self.graph = graph
        self.running: set[str] = set()
        self.cancelled: list[str] = []
        self.run_calls: list[dict] = []
        self.fail_stream = False

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
        return {"job": "scenario"}

    async def stream(self, conversation_id, need_history, job):
        if self.fail_stream:
            raise RuntimeError("stream failed")
        yield CompletionResponseDelta(
            message_id=str(uuid.uuid4()),
            delta=f"scenario:{conversation_id}:{need_history}:{job['job']}",
            is_thinking=False,
        )

    async def delete_conversation(self, conversation_id):
        self.running.discard(conversation_id)
        return await delete_conversation_record(self.session_factory, self.graph, conversation_id)


@pytest.fixture
def scenario_client(app_factory, sqlite_session_factory):
    graph = ScenarioGraph()
    runner = ScenarioRunner(sqlite_session_factory, graph)
    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.state.ConversationRunner = runner
    app.state.graph = graph
    app.include_router(conversation_router, prefix="/api")
    return TestClient(app, raise_server_exceptions=False), runner, graph


def _create_conversation(client: TestClient) -> str:
    response = client.post("/api/conversation")
    assert response.status_code == 200
    return response.json()["conversation_id"]


def test_user_chat_lifecycle_from_create_to_stream_search_pin_and_delete(
    scenario_client,
):
    client, runner, graph = scenario_client

    conversation_id = _create_conversation(client)
    completion = client.post(
        "/api/conversation/completion",
        json={
            "conversation_id": conversation_id,
            "request_id": str(uuid.uuid4()),
            "content": "Plan the sprint review",
            "created_at": 1,
            "attachments": [],
            "need_history": False,
        },
    )
    patch = client.patch(
        f"/api/conversation/{conversation_id}",
        json={"title": "Sprint Review", "is_pinned": True},
    )
    list_response = client.get("/api/conversations/", params={"page": 1, "page_size": 10})
    search_response = client.get("/api/conversations/search", params={"keywords": "Sprint", "page": 1, "page_size": 10})
    delete_response = client.delete(f"/api/conversation/{conversation_id}")

    assert completion.status_code == 200
    assert "event: delta" in completion.text
    assert runner.run_calls[0]["content"] == "Plan the sprint review"
    assert patch.status_code == 200
    assert list_response.status_code == 200
    assert list_response.json()["conversations"][0]["title"] == "Sprint Review"
    assert list_response.json()["conversations"][0]["is_pinned"] is True
    assert search_response.status_code == 200
    assert search_response.json()["conversations"][0]["conversation_id"] == conversation_id
    assert delete_response.status_code == 200
    assert graph.checkpointer.deleted_threads == [conversation_id]


def test_user_restarts_from_history_with_pending_attachment(
    scenario_client,
    sqlite_session_factory,
    run_async,
):
    client, runner, _graph = scenario_client
    conversation_id = _create_conversation(client)
    restart_message_id = str(uuid.uuid4())
    attachment_id = str(uuid.uuid4())
    stored_attachment_id = str(uuid.uuid4())

    async def _seed():
        async with sqlite_session_factory() as session:
            session.add(
                Message(
                    id=restart_message_id,
                    conversation_id=conversation_id,
                    seq=1,
                    content="old answer",
                )
            )
            session.add(
                Attachment(
                    id=stored_attachment_id,
                    hash="c" * 64,
                    path="/tmp/scenario.txt",
                    status="completed",
                )
            )
            session.add(
                MessageAttachment(
                    id=attachment_id,
                    message_id=None,
                    attachment_id=stored_attachment_id,
                    name="scenario.txt",
                )
            )
            await session.commit()

    run_async(_seed())

    response = client.post(
        "/api/conversation/completion",
        json={
            "conversation_id": conversation_id,
            "request_id": str(uuid.uuid4()),
            "content": "continue with this file",
            "created_at": 1,
            "attachments": [attachment_id],
            "need_history": True,
            "restart_message_id": restart_message_id,
        },
    )

    assert response.status_code == 200
    assert "event: delta" in response.text
    assert runner.run_calls == [
        {
            "conversation_id": conversation_id,
            "content": "continue with this file",
            "restart_message_id": restart_message_id,
            "attachments": [attachment_id],
        }
    ]


def test_user_cancels_running_completion_and_cannot_cancel_it_twice(scenario_client):
    client, runner, _graph = scenario_client
    conversation_id = _create_conversation(client)
    runner.running.add(conversation_id)

    cancelled = client.post("/api/conversation/cancelchat", params={"conversation_id": conversation_id})
    repeated = client.post("/api/conversation/cancelchat", params={"conversation_id": conversation_id})

    assert cancelled.status_code == 200
    assert cancelled.json() == {"status": "cancelled"}
    assert repeated.status_code == 400
    assert runner.cancelled == [conversation_id]


@pytest.mark.xfail(
    strict=True,
    reason="Known issue: completion stream exceptions currently escape as a 200 stream failure instead of a structured SSE error.",
)
def test_stream_failure_should_return_structured_sse_error(scenario_client):
    client, runner, _graph = scenario_client
    conversation_id = _create_conversation(client)
    runner.fail_stream = True

    response = client.post(
        "/api/conversation/completion",
        json={
            "conversation_id": conversation_id,
            "request_id": str(uuid.uuid4()),
            "content": "trigger stream failure",
            "created_at": 1,
            "attachments": [],
            "need_history": False,
        },
    )

    assert response.status_code == 200
    assert "event: error" in response.text
    assert "stream failed" in response.text
