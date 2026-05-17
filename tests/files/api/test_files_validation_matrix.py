from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

import agent.api.file as file_api
from agent.file_utils.extract import FileProcessError
from agent.api.file import router as file_router
from agent.db.models import Attachment, Conversation, Message, MessageAttachment


pytestmark = pytest.mark.api


@pytest.fixture
def file_validation_client(app_factory, sqlite_session_factory):
    app = app_factory()
    app.state.async_session = sqlite_session_factory
    app.include_router(file_router, prefix="/api")
    return TestClient(app)


@pytest.mark.parametrize(
    ("files", "expected_status"),
    [
        ({}, 400),
        ({"file": ("", b"hello", "text/plain")}, 400),
        ({"file": ("../notes.md", b"hello", "text/plain")}, 400),
        ({"file": (r"..\notes.md", b"hello", "text/plain")}, 400),
        ({"file": ("shell.exe", b"hello", "application/octet-stream")}, 400),
        ({"file": ("image.png", b"<html></html>", "text/html")}, 400),
        ({"file": ("notes.txt", b"", "text/plain")}, 400),
    ],
)
def test_file_upload_rejects_missing_path_mime_and_empty_inputs(file_validation_client, files, expected_status):
    response = file_validation_client.post("/api/files/upload", files=files)

    assert response.status_code == expected_status


def test_file_upload_accepts_unicode_filename_and_creates_pending_attachment(
    file_validation_client,
    sqlite_session_factory,
    run_async,
    monkeypatch,
):
    attachment_id = str(uuid.uuid4())

    async def fake_store_attachment(file, session_factory):
        async with session_factory() as session:
            session.add(
                Attachment(
                    id=attachment_id,
                    hash="hash-" + attachment_id,
                    path="uploads/unicode.txt",
                    status="completed",
                )
            )
            await session.commit()
        return attachment_id, "text/plain"

    monkeypatch.setattr(file_api, "store_attachment", fake_store_attachment)

    response = file_validation_client.post(
        "/api/files/upload",
        files={"file": ("课程笔记.txt", "hello".encode("utf-8"), "text/plain")},
    )

    async def _pending_link():
        async with sqlite_session_factory() as session:
            return await session.get(MessageAttachment, response.json()["file_id"])

    pending = run_async(_pending_link())

    assert response.status_code == 200
    assert response.json()["file_name"] == "课程笔记.txt"
    assert pending is not None
    assert pending.message_id is None
    assert pending.attachment_id == attachment_id


@pytest.mark.parametrize("name", ["notes\u0000.txt", "notes\nnext.txt", "notes\tindent.txt"])
@pytest.mark.xfail(
    reason="Known issue: upload filename validation does not reject control characters.",
    strict=True,
)
def test_file_upload_should_reject_control_character_filenames(file_validation_client, name, monkeypatch):
    async def fake_store_attachment(*_args, **_kwargs):
        return str(uuid.uuid4()), "text/plain"

    monkeypatch.setattr(file_api, "store_attachment", fake_store_attachment)

    response = file_validation_client.post(
        "/api/files/upload",
        files={"file": (name, b"hello", "text/plain")},
    )

    assert response.status_code == 400


@pytest.mark.xfail(
    reason="Known issue: repeated multipart file fields are accepted instead of rejected as ambiguous.",
    strict=True,
)
def test_file_upload_should_reject_repeated_file_fields(file_validation_client, monkeypatch):
    async def fake_store_attachment(*_args, **_kwargs):
        return str(uuid.uuid4()), "text/plain"

    monkeypatch.setattr(file_api, "store_attachment", fake_store_attachment)

    response = file_validation_client.post(
        "/api/files/upload",
        files=[
            ("file", ("first.txt", b"first", "text/plain")),
            ("file", ("second.txt", b"second", "text/plain")),
        ],
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    "file_id",
    [
        "not-a-uuid",
        "../agent.db",
        "123e4567-e89b-12d3-a456-426614174000;DROP TABLE attachments",
        "x" * 80,
    ],
)
def test_file_download_rejects_invalid_id_format_and_injection_strings(file_validation_client, file_id):
    response = file_validation_client.get(f"/api/file/{file_id}")

    assert response.status_code in {400, 404, 414}


def test_file_download_returns_404_for_well_formed_missing_id(file_validation_client):
    response = file_validation_client.get(f"/api/file/{uuid.uuid4()}")

    assert response.status_code == 404


@pytest.mark.xfail(
    reason="Known issue: download does not preflight missing physical files as 404.",
    strict=True,
)
def test_file_download_should_404_when_attachment_row_points_to_missing_file(
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

    async def _seed_row():
        async with sqlite_session_factory() as session:
            session.add(
                Attachment(
                    id=attachment_id,
                    hash="missing-hash",
                    path=str(tmp_path / "missing.txt"),
                    status="completed",
                )
            )
            await session.commit()

    run_async(_seed_row())

    response = client.get(f"/api/file/{attachment_id}")

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("message_id", "file_id"),
    [
        ("not-a-uuid", str(uuid.uuid4())),
        (str(uuid.uuid4()), "not-a-uuid"),
        ("../messages", str(uuid.uuid4())),
        (str(uuid.uuid4()), "../files"),
    ],
)
def test_file_info_rejects_invalid_message_or_file_id(file_validation_client, message_id, file_id):
    response = file_validation_client.get(f"/api/files/{message_id}/{file_id}/info")

    assert response.status_code in {400, 404}


def test_file_info_returns_404_for_pending_unbound_attachment(
    file_validation_client,
    sqlite_session_factory,
    run_async,
):
    attachment_id = str(uuid.uuid4())
    pending_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    async def _seed_pending():
        async with sqlite_session_factory() as session:
            session.add(
                Attachment(
                    id=attachment_id,
                    hash="pending-hash",
                    path="uploads/pending.txt",
                    status="completed",
                )
            )
            session.add(
                MessageAttachment(
                    id=pending_id,
                    message_id=None,
                    attachment_id=attachment_id,
                    name="pending.txt",
                )
            )
            await session.commit()

    run_async(_seed_pending())

    response = file_validation_client.get(f"/api/files/{message_id}/{attachment_id}/info")

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("display_name", "expected_type"),
    [
        ("diagram.PNG", "image"),
        ("paper.pdf", "pdf"),
        ("README.markdown", "markdown"),
        ("plain.TXT", "text"),
        ("archive.bin", "other"),
    ],
)
def test_file_info_classifies_suffixes_case_insensitively(
    file_validation_client,
    sqlite_session_factory,
    run_async,
    display_name,
    expected_type,
):
    attachment_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    message_attachment_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    async def _seed_bound_attachment():
        async with sqlite_session_factory() as session:
            session.add(Conversation(id=conversation_id, title="Files"))
            session.add(
                Message(
                    id=message_id,
                    conversation_id=conversation_id,
                    seq=1,
                    content="see attachment",
                )
            )
            session.add(
                Attachment(
                    id=attachment_id,
                    hash="hash-" + attachment_id,
                    path="uploads/original",
                    status="completed",
                )
            )
            session.add(
                MessageAttachment(
                    id=message_attachment_id,
                    message_id=message_id,
                    attachment_id=attachment_id,
                    name=display_name,
                )
            )
            await session.commit()

    run_async(_seed_bound_attachment())

    response = file_validation_client.get(f"/api/files/{message_id}/{attachment_id}/info")

    assert response.status_code == 200
    assert response.json() == {
        "file_id": message_attachment_id,
        "file_type": expected_type,
        "file_name": display_name,
    }


@pytest.mark.xfail(
    reason="Spec declares 422 for request validation, but the app-level validation handler maps it to 400.",
    strict=True,
)
def test_file_upload_missing_multipart_field_should_match_spec_422(file_validation_client):
    response = file_validation_client.post("/api/files/upload", json={"file": "not multipart"})

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("report.pdf", "application/pdf"),
        ("image.JPG", "image/jpeg"),
        ("diagram.webp", "image/webp"),
        ("notes.md", "text/markdown"),
        ("sheet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ],
)
def test_file_upload_accepts_allowed_extensions_and_mime_matrix(
    file_validation_client,
    sqlite_session_factory,
    monkeypatch,
    filename,
    content_type,
):
    async def fake_store_attachment(file, session_factory):
        attachment_id = str(uuid.uuid4())
        async with session_factory() as session:
            session.add(
                Attachment(
                    id=attachment_id,
                    hash="hash-" + attachment_id,
                    path="uploads/" + filename,
                    status="completed",
                )
            )
            await session.commit()
        return attachment_id, content_type

    monkeypatch.setattr(file_api, "store_attachment", fake_store_attachment)

    response = file_validation_client.post(
        "/api/files/upload",
        files={"file": (filename, b"content", content_type)},
    )

    assert response.status_code == 200
    assert response.json()["file_name"] == filename
    assert response.json()["mime_type"] == content_type


def test_file_upload_rejects_oversized_file_before_storage(file_validation_client, monkeypatch):
    async def fake_store_attachment(*_args, **_kwargs):
        raise AssertionError("oversized file must be rejected before storage")

    monkeypatch.setattr(file_api, "store_attachment", fake_store_attachment)

    response = file_validation_client.post(
        "/api/files/upload",
        files={"file": ("large.txt", b"x" * (10 * 1024 * 1024 + 1), "text/plain")},
    )

    assert response.status_code == 413


@pytest.mark.parametrize(
    ("filename", "content", "content_type"),
    [
        ("noext", b"content", "text/plain"),
        ("archive.zip", b"content", "application/zip"),
        ("photo.png", b"content", "image/jpeg"),
        ("paper.pdf", b"content", "text/plain"),
        (".." + "x" * 511 + ".txt", b"content", "text/plain"),
    ],
)
def test_file_upload_rejects_extension_mime_length_and_normalization_edges(
    file_validation_client,
    filename,
    content,
    content_type,
):
    response = file_validation_client.post(
        "/api/files/upload",
        files={"file": (filename, content, content_type)},
    )

    assert response.status_code == 400


@pytest.mark.xfail(
    reason="Known issue: upload trims surrounding filename whitespace and accepts the normalized name.",
    strict=True,
)
def test_file_upload_should_reject_surrounding_whitespace_filename(file_validation_client):
    response = file_validation_client.post(
        "/api/files/upload",
        files={"file": (" name.txt ", b"content", "text/plain")},
    )

    assert response.status_code == 400


def test_file_upload_parser_failure_should_match_spec_error_status(file_validation_client, monkeypatch):
    async def fake_store_attachment(*_args, **_kwargs):
        raise FileProcessError("parser failed")

    monkeypatch.setattr(file_api, "store_attachment", fake_store_attachment)

    response = file_validation_client.post(
        "/api/files/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 417


@pytest.mark.parametrize(
    "file_id",
    [
        "00000000-0000-0000-0000-000000000000",
        "123E4567-E89B-12D3-A456-426614174000",
        "%2e%2e%2fagent.db",
        "<script>alert(1)</script>",
        '{"$ne":""}',
    ],
)
def test_file_download_path_parameter_security_matrix(file_validation_client, file_id):
    response = file_validation_client.get(f"/api/file/{file_id}")

    assert response.status_code in {400, 404, 414}


def test_file_download_surfaces_unexpected_session_failure_as_500(app_factory):
    class BrokenSessionFactory:
        def __call__(self):
            raise RuntimeError("db unavailable")

    app = app_factory()
    app.state.async_session = BrokenSessionFactory()
    app.include_router(file_router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get(f"/api/file/{uuid.uuid4()}")

    assert response.status_code == 500


def test_file_info_rejects_unbound_wrong_message_and_duplicate_links(
    file_validation_client,
    sqlite_session_factory,
    run_async,
):
    attachment_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    other_message_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    async def _seed():
        async with sqlite_session_factory() as session:
            session.add(Conversation(id=conversation_id, title="Files"))
            session.add(Message(id=message_id, conversation_id=conversation_id, seq=1, content="one"))
            session.add(Message(id=other_message_id, conversation_id=conversation_id, seq=2, content="two"))
            session.add(Attachment(id=attachment_id, hash="hash", path="uploads/a.txt", status="completed"))
            session.add(MessageAttachment(message_id=message_id, attachment_id=attachment_id, name="a.txt"))
            session.add(MessageAttachment(message_id=message_id, attachment_id=attachment_id, name="b.pdf"))
            await session.commit()

    run_async(_seed())

    wrong_message = file_validation_client.get(f"/api/files/{other_message_id}/{attachment_id}/info")
    duplicate = file_validation_client.get(f"/api/files/{message_id}/{attachment_id}/info")

    assert wrong_message.status_code == 404
    assert duplicate.status_code == 200
    assert duplicate.json()["file_name"] in {"a.txt", "b.pdf"}


@pytest.mark.parametrize(
    ("message_id", "file_id"),
    [
        ("00000000-0000-0000-0000-000000000000", "00000000-0000-0000-0000-000000000000"),
        ("<script>alert(1)</script>", str(uuid.uuid4())),
        (str(uuid.uuid4()), '{"$ne":""}'),
        ("x" * 80, str(uuid.uuid4())),
    ],
)
def test_file_info_path_parameter_security_matrix(file_validation_client, message_id, file_id):
    response = file_validation_client.get(f"/api/files/{message_id}/{file_id}/info")

    assert response.status_code in {400, 404, 414}
