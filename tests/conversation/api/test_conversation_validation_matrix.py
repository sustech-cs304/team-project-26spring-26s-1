from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

import agent.api.conversation as conversation_api
from agent.api.conversation import router as conversation_router
from agent.api.conversation_models import CompletionResponseDelta
from agent.db.models import Attachment, Conversation, Message, MessageAttachment


pytestmark = pytest.mark.api


class MinimalConversationRunner:
    def __init__(self):
        self.running: set[str] = set()
        self.cancelled: list[str] = []
        self.run_calls: list[dict] = []

    def is_running(self, _conversation_id):
        return _conversation_id in self.running

    async def cancel(self, conversation_id):
        self.cancelled.append(conversation_id)
        self.running.discard(conversation_id)

    async def run(self, conversation_id, content, restart_message_id=None, attachments=None):
        self.run_calls.append(
            {
                "conversation_id": conversation_id,
                "content": content,
                "restart_message_id": restart_message_id,
                "attachments": attachments,
            }
        )
        return {"job": "fake"}

    async def stream(self, conversation_id, need_history, job):
        yield CompletionResponseDelta(
            message_id="message-1",
            delta=f"ok:{conversation_id}:{need_history}:{job['job']}",
            is_thinking=False,
        )


class ExplodingConversationRunner(MinimalConversationRunner):
    async def run(self, *_args, **_kwargs):
        raise RuntimeError("runner unavailable")


class ExplodingSessionFactory:
    def __call__(self):
        return self

    async def __aenter__(self):
        raise RuntimeError("database unavailable")

    async def __aexit__(self, *_args):
        return False


@pytest.fixture
def conversation_validation_client(app_factory, sqlite_session_factory):
    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.state.ConversationRunner = MinimalConversationRunner()
    app.state.graph = object()
    app.include_router(conversation_router, prefix="/api")
    return TestClient(app), app.state.ConversationRunner


@pytest.fixture
def conversation_error_client(app_factory):
    app = app_factory()
    app.state.async_session = ExplodingSessionFactory()
    app.state.ConversationRunner = ExplodingConversationRunner()
    app.state.graph = object()
    app.include_router(conversation_router, prefix="/api")
    return TestClient(app, raise_server_exceptions=False)


def _create_conversation(client: TestClient) -> str:
    create = client.post("/api/conversation")
    assert create.status_code == 200
    return create.json()["conversation_id"]


def _completion_payload(conversation_id: str, **overrides):
    payload = {
        "conversation_id": conversation_id,
        "request_id": str(uuid.uuid4()),
        "content": "hello",
        "attachments": [],
        "need_history": False,
        "restart_message_id": None,
    }
    payload.update(overrides)
    return payload


def _seed_message(sqlite_session_factory, run_async, conversation_id: str) -> str:
    message_id = str(uuid.uuid4())

    async def _seed():
        async with sqlite_session_factory() as session:
            session.add(Message(id=message_id, conversation_id=conversation_id, seq=1, content="prior message"))
            await session.commit()

    run_async(_seed())
    return message_id


def _seed_pending_attachment(sqlite_session_factory, run_async) -> str:
    attachment_id = str(uuid.uuid4())
    pending_id = str(uuid.uuid4())

    async def _seed():
        async with sqlite_session_factory() as session:
            session.add(Attachment(id=attachment_id, hash="h" * 64, path="dummy.txt", status="completed"))
            session.add(
                MessageAttachment(
                    id=pending_id,
                    message_id=None,
                    attachment_id=attachment_id,
                    name="dummy.txt",
                )
            )
            await session.commit()

    run_async(_seed())
    return pending_id


@pytest.mark.parametrize(
    "payload",
    [
        {"request_id": str(uuid.uuid4()), "attachments": [], "need_history": False},
        {"conversation_id": str(uuid.uuid4()), "attachments": [], "need_history": False},
        {"conversation_id": str(uuid.uuid4()), "request_id": str(uuid.uuid4()), "attachments": []},
        {"conversation_id": str(uuid.uuid4()), "request_id": str(uuid.uuid4()), "attachments": "file-1", "need_history": False},
        {"conversation_id": str(uuid.uuid4()), "request_id": str(uuid.uuid4()), "attachments": [], "need_history": "maybe"},
        {"conversation_id": str(uuid.uuid4()), "request_id": "not-a-uuid", "attachments": [], "need_history": False},
        {"conversation_id": "not-a-uuid", "request_id": str(uuid.uuid4()), "attachments": [], "need_history": False},
        {
            "conversation_id": str(uuid.uuid4()),
            "request_id": str(uuid.uuid4()),
            "created_at": 1,
            "content": "hello",
            "attachments": [],
            "need_history": False,
        },
    ],
)
@pytest.mark.xfail(
    strict=True,
    reason="Spec declares 422 for request validation errors; current test app maps them to 400.",
)
def test_conversation_completion_rejects_missing_and_wrong_type_inputs(conversation_validation_client, payload):
    client, _runner = conversation_validation_client

    response = client.post("/api/conversation/completion", json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize("json_body", [None, {}])
@pytest.mark.xfail(
    strict=True,
    reason="Spec declares 422 for missing/invalid JSON bodies; current test app maps them to 400.",
)
def test_conversation_completion_rejects_null_and_empty_body(conversation_validation_client, json_body):
    client, _runner = conversation_validation_client

    response = client.post("/api/conversation/completion", json=json_body)

    assert response.status_code == 422


@pytest.mark.xfail(
    strict=True,
    reason="Spec declares 422 for malformed JSON; current test app maps request validation to 400.",
)
def test_conversation_completion_rejects_malformed_json_body_as_spec_422(conversation_validation_client):
    client, _runner = conversation_validation_client

    response = client.post(
        "/api/conversation/completion",
        content="{",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422


def test_conversation_completion_accepts_content_history_restart_and_attachment_boundaries(
    conversation_validation_client,
    sqlite_session_factory,
    run_async,
):
    client, runner = conversation_validation_client
    conversation_id = _create_conversation(client)
    message_id = _seed_message(sqlite_session_factory, run_async, conversation_id)
    pending_id = _seed_pending_attachment(sqlite_session_factory, run_async)

    payloads = [
        (_completion_payload(conversation_id, content=None, need_history=True), {"content": "", "attachments": [], "restart_message_id": None}),
        (_completion_payload(conversation_id, content="", need_history=True, restart_message_id=message_id), {"content": "", "attachments": [], "restart_message_id": message_id}),
        (_completion_payload(conversation_id, content="x" * 20_000), {"content": "x" * 20_000, "attachments": [], "restart_message_id": None}),
        (_completion_payload(conversation_id, content="with files", attachments=[pending_id]), {"content": "with files", "attachments": [pending_id], "restart_message_id": None}),
    ]

    for payload, expected_call in payloads:
        with client.stream("POST", "/api/conversation/completion", json=payload) as stream:
            stream_text = stream.read().decode("utf-8")

        assert "event: delta" in stream_text
        assert runner.run_calls[-1] == {"conversation_id": conversation_id, **expected_call}


@pytest.mark.parametrize(
    "content",
    [
        "' OR 1=1 --",
        "<script>alert(1)</script>",
        "$(touch /tmp/opencrab)",
        '{"$ne": null}',
        "A" * 32768,
        "模糊输入\x00with-control",
    ],
    ids=["sql", "xss", "command", "nosql-json", "very-long", "fuzz-control"],
)
def test_conversation_completion_treats_security_and_fuzz_content_as_data(
    conversation_validation_client,
    content,
):
    client, runner = conversation_validation_client
    conversation_id = _create_conversation(client)

    with client.stream(
        "POST",
        "/api/conversation/completion",
        json=_completion_payload(conversation_id, content=content, need_history=True),
    ) as stream:
        stream_text = stream.read().decode("utf-8")

    if len(content) > 20_000:
        assert "Invalid request parameters" in stream_text
        return
    assert "event: delta" in stream_text
    assert runner.run_calls[-1]["content"] == content


def test_conversation_completion_should_return_429_when_conversation_is_already_running(
    conversation_validation_client,
):
    client, runner = conversation_validation_client
    conversation_id = _create_conversation(client)
    runner.running.add(conversation_id)

    response = client.post(
        "/api/conversation/completion",
        json=_completion_payload(conversation_id),
    )

    assert response.status_code == 429


def test_create_conversation_accepts_absent_body_and_ignores_unmodeled_body(conversation_validation_client):
    client, _runner = conversation_validation_client

    no_body = client.post("/api/conversation")
    with_body = client.post(
        "/api/conversation",
        json={"title": "<script>alert(1)</script>", "unexpected": {"$ne": None}},
    )

    assert no_body.status_code == 200
    assert set(no_body.json()) == {"conversation_id", "created_at"}
    assert with_body.status_code == 200
    assert set(with_body.json()) == {"conversation_id", "created_at"}


def test_create_conversation_returns_500_when_database_dependency_fails(conversation_error_client):
    response = conversation_error_client.post("/api/conversation")

    assert response.status_code == 500


@pytest.mark.parametrize(
    "attachments",
    [
        [1],
        [{"id": "file-1"}],
        [None],
    ],
)
@pytest.mark.xfail(
    strict=True,
    reason="Spec declares 422 for array item type errors; current test app maps them to 400.",
)
def test_conversation_completion_rejects_malformed_attachment_items(conversation_validation_client, attachments):
    client, _runner = conversation_validation_client
    conversation_id = _create_conversation(client)

    response = client.post(
        "/api/conversation/completion",
        json=_completion_payload(conversation_id, attachments=attachments),
    )

    assert response.status_code == 422


@pytest.mark.parametrize("restart_message_id", ["../message", "message-1; DROP TABLE messages", "\x00message"])
def test_conversation_completion_should_reject_unsafe_restart_message_ids(
    conversation_validation_client,
    restart_message_id,
):
    client, _runner = conversation_validation_client
    conversation_id = _create_conversation(client)

    response = client.post(
        "/api/conversation/completion",
        json=_completion_payload(conversation_id, restart_message_id=restart_message_id),
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"page": 1, "page_size": 25},
        {"page": 1, "page_size": 1},
        {"page": 999999, "page_size": 25},
        {"page": 1, "page_size": 25, "keywords": "' OR 1=1 --"},
    ],
)
def test_conversation_list_accepts_spec_optional_query_and_boundaries(conversation_validation_client, params):
    client, _runner = conversation_validation_client

    response = client.get("/api/conversations/", params=params)

    assert response.status_code == 200
    assert "conversations" in response.json()


@pytest.mark.xfail(
    strict=True,
    reason="Spec declares 422 for query type errors; current test app maps request validation to 400.",
)
@pytest.mark.parametrize("params", [{"page": "abc"}, {"page_size": "abc"}, {"page": ""}, {"page_size": ""}])
def test_conversation_list_should_reject_query_type_errors_as_spec_422(conversation_validation_client, params):
    client, _runner = conversation_validation_client

    response = client.get("/api/conversations/", params=params)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"keywords": "", "page": 1, "page_size": 25}, 400),
        ({"keywords": "   ", "page": 1, "page_size": 25}, 400),
        ({"keywords": "project", "page": 0, "page_size": 25}, 400),
        ({"keywords": "project", "page": 1, "page_size": 0}, 400),
        ({"keywords": "project", "page": 1, "page_size": 101}, 400),
        ({"keywords": "x" * 201, "page": 1, "page_size": 25}, 400),
        ({"keywords": "' OR 1=1 --", "page": 1, "page_size": 25}, 200),
        ({"keywords": "<script>alert(1)</script>", "page": 1, "page_size": 25}, 200),
    ],
)
def test_conversation_search_validates_required_pagination_and_treats_injection_as_data(
    conversation_validation_client,
    params,
    expected,
):
    client, _runner = conversation_validation_client

    response = client.get("/api/conversations/search", params=params)

    assert response.status_code == expected


@pytest.mark.parametrize("params", [{"page": 0}, {"page": 1, "page_size": 0}, {"page": -1, "page_size": 25}, {"page": 1, "page_size": 101}])
def test_conversation_list_should_reject_invalid_pagination(conversation_validation_client, params):
    client, _runner = conversation_validation_client

    response = client.get("/api/conversations/", params=params)

    assert response.status_code == 400


def test_conversation_list_paginates_without_external_resources(
    conversation_validation_client,
    sqlite_session_factory,
    run_async,
):
    client, _runner = conversation_validation_client

    async def _seed():
        async with sqlite_session_factory() as session:
            session.add_all([Conversation(id=str(uuid.uuid4()), title=f"Chat {i}") for i in range(3)])
            await session.commit()

    run_async(_seed())

    first_page = client.get("/api/conversations/", params={"page": 1, "page_size": 2})
    second_page = client.get("/api/conversations/", params={"page": 2, "page_size": 2})

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert len(first_page.json()["conversations"]) == 2
    assert len(second_page.json()["conversations"]) == 1


def test_conversation_list_does_not_support_page_size_alias(conversation_validation_client):
    client, _runner = conversation_validation_client

    response = client.get("/api/conversations/", params={"page": 1, "pageSize": 0})

    assert response.status_code == 200


@pytest.mark.xfail(
    strict=True,
    reason="Spec declares 422 for search query type errors; current test app maps request validation to 400.",
)
@pytest.mark.parametrize("params", [{"keywords": "project", "page": "abc"}, {"keywords": "project", "page_size": ""}])
def test_conversation_search_should_reject_query_type_errors_as_spec_422(conversation_validation_client, params):
    client, _runner = conversation_validation_client

    response = client.get("/api/conversations/search", params=params)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "keywords",
    [
        "' OR 1=1 --",
        "<script>alert(1)</script>",
        "项目\x00控制",
        "unicode 课程 ✅",
    ],
)
def test_conversation_search_treats_security_and_unicode_keywords_as_data(
    conversation_validation_client,
    sqlite_session_factory,
    run_async,
    keywords,
):
    client, _runner = conversation_validation_client

    async def _seed():
        async with sqlite_session_factory() as session:
            conv_id = str(uuid.uuid4())
            session.add(Conversation(id=conv_id, title="ordinary sprint notes"))
            session.add(Message(id=str(uuid.uuid4()), conversation_id=conv_id, seq=1, content="plain content"))
            await session.commit()

    run_async(_seed())

    response = client.get("/api/conversations/search", params={"keywords": keywords, "page": 1, "page_size": 25})

    assert response.status_code == 200
    assert response.json()["conversations"] == []


def test_conversation_search_returns_500_when_search_dependency_fails(conversation_validation_client, monkeypatch):
    client, _runner = conversation_validation_client

    async def _raise(*_args, **_kwargs):
        raise RuntimeError("search backend failed")

    monkeypatch.setattr(conversation_api, "search_conversations_record", _raise)

    response = client.get("/api/conversations/search", params={"keywords": "project", "page": 1, "page_size": 25})

    assert response.status_code == 500


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "<script>alert(1)</script>"},
        {"is_pinned": True},
    ],
)
def test_conversation_patch_accepts_current_title_and_pin_inputs(conversation_validation_client, payload):
    client, _runner = conversation_validation_client
    conversation_id = _create_conversation(client)

    response = client.patch(f"/api/conversation/{conversation_id}", json=payload)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "A"},
        {"title": "Pinned conversation title with unicode 课程"},
        {"title": "x" * 64, "is_pinned": False},
    ],
)
def test_conversation_patch_accepts_spec_nullable_and_boundary_payloads(conversation_validation_client, payload):
    client, _runner = conversation_validation_client
    conversation_id = _create_conversation(client)

    response = client.patch(f"/api/conversation/{conversation_id}", json=payload)

    assert response.status_code == 200


@pytest.mark.parametrize("payload", [{"title": None}, {"is_pinned": None}])
def test_conversation_patch_rejects_null_only_payloads(conversation_validation_client, payload):
    client, _runner = conversation_validation_client
    conversation_id = _create_conversation(client)

    response = client.patch(f"/api/conversation/{conversation_id}", json=payload)

    assert response.status_code == 400


def test_conversation_patch_rejects_missing_conversation(conversation_validation_client):
    client, _runner = conversation_validation_client

    response = client.patch(f"/api/conversation/{uuid.uuid4()}", json={"title": "Valid title"})

    assert response.status_code == 404


@pytest.mark.xfail(
    strict=True,
    reason="Spec declares 422 for missing request bodies; current test app maps validation to 400.",
)
@pytest.mark.parametrize("body", [None, [], "not-object"])
def test_conversation_patch_should_reject_invalid_body_shapes_as_spec_422(conversation_validation_client, body):
    client, _runner = conversation_validation_client
    conversation_id = _create_conversation(client)

    response = client.patch(f"/api/conversation/{conversation_id}", json=body)

    assert response.status_code == 422


def test_conversation_patch_should_reject_empty_body(conversation_validation_client):
    client, _runner = conversation_validation_client
    conversation_id = _create_conversation(client)

    response = client.patch(f"/api/conversation/{conversation_id}", json={})

    assert response.status_code == 400


def test_conversation_patch_should_reject_title_above_spec_max_length(conversation_validation_client):
    client, _runner = conversation_validation_client
    conversation_id = _create_conversation(client)

    response = client.patch(f"/api/conversation/{conversation_id}", json={"title": "x" * 65})

    assert response.status_code == 400


def test_conversation_patch_should_reject_non_boolean_is_pinned(conversation_validation_client):
    client, _runner = conversation_validation_client
    conversation_id = _create_conversation(client)

    response = client.patch(f"/api/conversation/{conversation_id}", json={"is_pinned": "true"})

    assert response.status_code == 400


@pytest.mark.parametrize(
    "title",
    ["' OR 1=1 --", "<script>alert(1)</script>", "$(shutdown now)", '{"$ne":null}', "模糊\x00输入"],
    ids=["sql", "xss", "command", "nosql-json", "fuzz-control"],
)
def test_conversation_patch_treats_security_title_strings_as_data(conversation_validation_client, title):
    client, _runner = conversation_validation_client
    conversation_id = _create_conversation(client)

    response = client.patch(f"/api/conversation/{conversation_id}", json={"title": title})

    assert response.status_code == 200


@pytest.mark.xfail(
    strict=True,
    reason="Spec declares 422 for missing required query parameters; current test app maps validation to 400.",
)
def test_conversation_cancel_should_reject_missing_query_as_spec_422(conversation_validation_client):
    client, _runner = conversation_validation_client

    response = client.post("/api/conversation/cancelchat")

    assert response.status_code == 422


def test_conversation_cancel_cancels_running_chat_and_rejects_repeated_cancel(conversation_validation_client):
    client, runner = conversation_validation_client
    conversation_id = _create_conversation(client)
    runner.running.add(conversation_id)

    cancelled = client.post("/api/conversation/cancelchat", params={"conversation_id": conversation_id})
    second_cancel = client.post("/api/conversation/cancelchat", params={"conversation_id": conversation_id})

    assert cancelled.status_code == 200
    assert cancelled.json() == {"status": "cancelled"}
    assert second_cancel.status_code == 400
    assert runner.cancelled == [conversation_id]


def test_conversation_cancel_should_report_nonexistent_conversation(conversation_validation_client):
    client, _runner = conversation_validation_client

    response = client.post("/api/conversation/cancelchat", params={"conversation_id": str(uuid.uuid4())})

    assert response.status_code == 404


@pytest.mark.parametrize("conversation_id", ["../conversation", "' OR 1=1 --", '{"$ne":null}', "\x00bad"])
def test_conversation_cancel_should_reject_unsafe_running_conversation_ids(
    conversation_validation_client,
    conversation_id,
):
    client, runner = conversation_validation_client
    runner.running.add(conversation_id)

    response = client.post("/api/conversation/cancelchat", params={"conversation_id": conversation_id})

    assert response.status_code == 400


def test_conversation_delete_reports_unknown_uuid_as_404(
    conversation_validation_client,
):
    client, _runner = conversation_validation_client

    response = client.delete(f"/api/conversation/{uuid.uuid4()}")

    assert response.status_code == 404


@pytest.mark.parametrize("conversation_id", ["missing", "' OR 1=1 --", '{"$ne":null}'])
def test_conversation_delete_rejects_unsafe_ids_as_400(conversation_validation_client, conversation_id):
    client, _runner = conversation_validation_client

    response = client.delete(f"/api/conversation/{conversation_id}")

    assert response.status_code == 400


@pytest.mark.xfail(
    strict=True,
    reason="Spec BadRequest covers path traversal identifiers; current routing normalizes the slash and returns 405.",
)
def test_conversation_delete_should_reject_path_traversal_identifier(conversation_validation_client):
    client, _runner = conversation_validation_client

    response = client.delete("/api/conversation/../conversation")

    assert response.status_code == 400


@pytest.mark.parametrize("restart_message_id", ["../message", "' OR 1=1 --", '{"$ne":null}', "\x00bad"])
def test_conversation_delete_should_reject_unsafe_restart_message_id(
    conversation_validation_client,
    restart_message_id,
):
    client, _runner = conversation_validation_client
    conversation_id = _create_conversation(client)

    response = client.delete(
        f"/api/conversation/{conversation_id}",
        params={"restart_message_id": restart_message_id},
    )

    assert response.status_code == 400


@pytest.mark.xfail(strict=True, reason="Known issue: delete does not guard against deleting an active running conversation.")
def test_conversation_delete_should_reject_running_conversation(conversation_validation_client):
    client, runner = conversation_validation_client
    conversation_id = _create_conversation(client)
    runner.running.add(conversation_id)

    response = client.delete(f"/api/conversation/{conversation_id}")

    assert response.status_code in {400, 409}
