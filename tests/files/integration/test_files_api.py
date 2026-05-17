from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

import agent.api.file as file_api
from agent.api.file import router as file_router
from agent.db.models import Attachment, Conversation, Message, MessageAttachment


pytestmark = pytest.mark.integration


def test_file_api_downloads_attachment_and_returns_bound_file_info(
    app_factory,
    sqlite_session_factory,
    run_async,
    tmp_path,
):
    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.include_router(file_router, prefix="/api")
    client = TestClient(app)

    file_path = tmp_path / "notes.md"
    file_path.write_text("hello", encoding="utf-8")

    attachment_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    message_attachment_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    async def _seed_rows():
        async with sqlite_session_factory() as session:
            conversation = Conversation(id=conversation_id, title="Test conversation")
            message = Message(
                id=message_id,
                conversation_id=conversation_id,
                seq=1,
                content="hello",
            )
            attachment = Attachment(
                id=attachment_id,
                hash="hash",
                path=str(file_path),
                status="completed",
            )
            link = MessageAttachment(
                id=message_attachment_id,
                message_id=message_id,
                attachment_id=attachment_id,
                name="notes.md",
            )
            session.add_all([conversation, message, attachment, link])
            await session.commit()

    run_async(_seed_rows())

    downloaded = client.get(f"/api/file/{attachment_id}")
    info = client.get(f"/api/files/{message_id}/{attachment_id}/info")
    invalid = client.get("/api/file/not-a-uuid")

    assert downloaded.status_code == 200
    assert downloaded.content == b"hello"
    assert info.status_code == 200
    assert info.json() == {
        "file_id": message_attachment_id,
        "file_type": "markdown",
        "file_name": "notes.md",
    }
    assert invalid.status_code == 400


def test_file_upload_api_validates_multipart_and_creates_pending_message_attachment(
    app_factory,
    sqlite_session_factory,
    monkeypatch,
):
    async def fake_store_attachment(file, session_factory):
        attachment_id = str(uuid.uuid4())
        async with session_factory() as session:
            session.add(
                Attachment(
                    id=attachment_id,
                    hash="hash-" + attachment_id,
                    path="uploads/notes.txt",
                    status="completed",
                )
            )
            await session.commit()
        return attachment_id, "text/plain"

    monkeypatch.setattr(file_api, "store_attachment", fake_store_attachment)

    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.include_router(file_router, prefix="/api")
    client = TestClient(app)

    uploaded = client.post(
        "/api/files/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    bad_name = client.post(
        "/api/files/upload",
        files={"file": ("../notes.txt", b"hello", "text/plain")},
    )
    empty = client.post(
        "/api/files/upload",
        files={"file": ("notes.txt", b"", "text/plain")},
    )

    assert uploaded.status_code == 200
    payload = uploaded.json()
    assert payload["mime_type"] == "text/plain"
    assert payload["file_name"] == "notes.txt"
    uuid.UUID(payload["file_id"])
    assert bad_name.status_code == 400
    assert empty.status_code == 400
