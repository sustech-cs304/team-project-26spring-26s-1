from __future__ import annotations

import pytest
from fastapi import HTTPException

from agent.file_utils.utils import (
    _validate_upload_extension_and_mime,
    _validate_upload_filename,
    validate_file_id,
)


pytestmark = pytest.mark.unit


def test_file_id_validator_requires_canonical_uuid_and_rejects_injection_inputs():
    file_id = "123e4567-e89b-12d3-a456-426614174000"
    assert validate_file_id(file_id) == file_id
    assert validate_file_id("123E4567-E89B-12D3-A456-426614174000") == file_id

    for raw in [
        "",
        "../agent.db",
        "123e4567-e89b-12d3-a456-426614174000;DROP TABLE attachments",
        "x" * 80,
    ]:
        with pytest.raises(HTTPException):
            validate_file_id(raw)


def test_upload_filename_and_mime_validation_rejects_path_and_content_type_spoofing():
    assert _validate_upload_filename("notes.md") == "notes.md"
    assert _validate_upload_extension_and_mime("notes.md", "text/plain; charset=utf-8") == ".md"

    for name in ["../notes.md", r"..\notes.md", "", ".", "x" * 513 + ".txt"]:
        with pytest.raises(HTTPException):
            _validate_upload_filename(name)

    with pytest.raises(HTTPException):
        _validate_upload_extension_and_mime("shell.exe", "application/octet-stream")

    with pytest.raises(HTTPException):
        _validate_upload_extension_and_mime("image.png", "text/html")
