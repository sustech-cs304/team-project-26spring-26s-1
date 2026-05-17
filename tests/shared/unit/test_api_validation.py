from __future__ import annotations

import pytest
from fastapi import HTTPException, params, status
from pydantic import BaseModel, ValidationError

from agent.api.validation import (
    UUID_PATTERN,
    UUIDPath,
    UUIDQuery,
    UUIDString,
    bad_request,
    canonical_uuid,
    canonical_uuid_or_bad_request,
    require_unique,
)


pytestmark = pytest.mark.unit


class UUIDBodyModel(BaseModel):
    item_id: UUIDString


def test_uuid_string_type_exposes_shared_openapi_constraints():
    schema = UUIDBodyModel.model_json_schema()

    assert schema["properties"]["item_id"]["maxLength"] == 36
    assert schema["properties"]["item_id"]["pattern"] == UUID_PATTERN


def test_uuid_route_aliases_expose_shared_fastapi_constraints():
    assert isinstance(UUIDPath.__metadata__[0], params.Path)
    assert any(getattr(item, "max_length", None) == 36 for item in UUIDPath.__metadata__[0].metadata)
    assert any(getattr(item, "pattern", None) == UUID_PATTERN for item in UUIDPath.__metadata__[0].metadata)

    assert isinstance(UUIDQuery.__metadata__[0], params.Query)
    assert any(getattr(item, "max_length", None) == 36 for item in UUIDQuery.__metadata__[0].metadata)
    assert any(getattr(item, "pattern", None) == UUID_PATTERN for item in UUIDQuery.__metadata__[0].metadata)


def test_canonical_uuid_accepts_and_normalizes_canonical_uuid_strings():
    assert canonical_uuid("123e4567-e89b-12d3-a456-426614174000") == (
        "123e4567-e89b-12d3-a456-426614174000"
    )
    assert canonical_uuid("123E4567-E89B-12D3-A456-426614174000") == (
        "123e4567-e89b-12d3-a456-426614174000"
    )


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not-a-uuid",
        "123e4567e89b12d3a456426614174000",
        "123e4567-e89b-12d3-a456-426614174000/../../x",
        "123e4567-e89b-12d3-a456-426614174000;DROP TABLE conversation",
        object(),
    ],
)
def test_canonical_uuid_rejects_invalid_or_noncanonical_inputs(raw):
    with pytest.raises(ValueError, match="conversation_id must be a canonical UUID string|must be a UUID string"):
        canonical_uuid(raw, "conversation_id")


def test_canonical_uuid_or_bad_request_wraps_validation_as_http_400():
    with pytest.raises(HTTPException) as exc_info:
        canonical_uuid_or_bad_request("../agent.db", "file_id")

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc_info.value.detail == {"message": "file_id must be a canonical UUID string"}


def test_bad_request_uses_consistent_error_shape():
    exc = bad_request("Invalid request parameters")

    assert exc.status_code == status.HTTP_400_BAD_REQUEST
    assert exc.detail == {"message": "Invalid request parameters"}


def test_require_unique_allows_unique_sequences_and_rejects_duplicates():
    require_unique(["a", "b", "c"], "values must be unique")

    with pytest.raises(ValueError, match="values must be unique"):
        require_unique(["a", "b", "a"], "values must be unique")


def test_uuid_string_body_constraint_rejects_uppercase_before_normalization():
    with pytest.raises(ValidationError):
        UUIDBodyModel(item_id="123E4567-E89B-12D3-A456-426614174000")
