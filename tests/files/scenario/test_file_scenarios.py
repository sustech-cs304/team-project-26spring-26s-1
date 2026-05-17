from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import agent.api.file as file_api
from agent.api.file import router as file_router
from agent.db.models import Attachment, Conversation, Message, MessageAttachment
from agent.file_utils.utils import bind_pending_message_attachments


pytestmark = pytest.mark.scenario


def test_upload_bind_info_and_download_file_lifecycle(
    app_factory,
    sqlite_session_factory,
    monkeypatch,
    run_async,
    tmp_path,
):
    stored_path = tmp_path / "scenario-notes.txt"
    stored_path.write_text("scenario file body", encoding="utf-8")

    async def fake_store_attachment(file, session_factory):
        attachment_id = str(uuid.uuid4())
        async with session_factory() as session:
            session.add(
                Attachment(
                    id=attachment_id,
                    hash="scenario-" + attachment_id,
                    path=str(stored_path),
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

    upload = client.post(
        "/api/files/upload",
        files={"file": ("scenario-notes.txt", b"scenario file body", "text/plain")},
    )
    pending_id = upload.json()["file_id"]
    conversation_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    async def _seed_message_and_bind():
        async with sqlite_session_factory() as session:
            session.add(Conversation(id=conversation_id, title="File scenario"))
            session.add(Message(id=message_id, conversation_id=conversation_id, seq=1, content="with file"))
            await session.commit()

        bound = await bind_pending_message_attachments(sqlite_session_factory, message_id, [pending_id])

        async with sqlite_session_factory() as session:
            result = await session.execute(
                select(MessageAttachment).where(MessageAttachment.id == pending_id)
            )
            row = result.scalar_one()
            return bound[0].attachment_id, row.message_id

    attachment_id, bound_message_id = run_async(_seed_message_and_bind())

    info = client.get(f"/api/files/{message_id}/{attachment_id}/info")
    download = client.get(f"/api/file/{attachment_id}")
    missing_info = client.get(f"/api/files/{uuid.uuid4()}/{attachment_id}/info")

    assert upload.status_code == 200
    assert upload.json()["file_name"] == "scenario-notes.txt"
    assert uuid.UUID(pending_id)
    assert bound_message_id == message_id
    assert info.status_code == 200
    assert info.json() == {
        "file_id": pending_id,
        "file_type": "text",
        "file_name": "scenario-notes.txt",
    }
    assert download.status_code == 200
    assert download.content == b"scenario file body"
    assert missing_info.status_code == 404


@pytest.mark.xfail(
    strict=True,
    reason="Known issue: download does not preflight missing physical files as 404.",
)
def test_download_missing_physical_file_should_return_404(
    app_factory,
    sqlite_session_factory,
    run_async,
    tmp_path,
):
    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.include_router(file_router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)
    attachment_id = str(uuid.uuid4())

    async def _seed_missing_file():
        async with sqlite_session_factory() as session:
            session.add(
                Attachment(
                    id=attachment_id,
                    hash="missing-file",
                    path=str(tmp_path / "missing.txt"),
                    status="completed",
                )
            )
            await session.commit()

    run_async(_seed_missing_file())

    response = client.get(f"/api/file/{attachment_id}")

    assert response.status_code == 404
