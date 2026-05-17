from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from agent.api.conversation import ConversationCompletionRequest, ConversationUpdateRequest


pytestmark = pytest.mark.unit


def _completion_payload(**overrides):
    payload = {
        "conversation_id": str(uuid.uuid4()),
        "request_id": str(uuid.uuid4()),
        "content": "hello",
        "attachments": [],
        "need_history": False,
        "restart_message_id": None,
    }
    payload.update(overrides)
    return payload


def test_completion_request_accepts_text_attachment_or_history_context():
    attachment_id = str(uuid.uuid4())

    assert ConversationCompletionRequest(**_completion_payload(content="hello")).content == "hello"
    assert ConversationCompletionRequest(
        **_completion_payload(content=None, attachments=[attachment_id])
    ).attachments == [attachment_id]
    assert ConversationCompletionRequest(
        **_completion_payload(content=None, attachments=[], need_history=True)
    ).need_history is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"conversation_id": "not-a-uuid"},
        {"request_id": "not-a-uuid"},
        {"restart_message_id": "not-a-uuid"},
        {"content": "x" * 20_001},
        {"attachments": [str(uuid.uuid4()) for _ in range(21)]},
        {"attachments": ["not-a-uuid"]},
        {"need_history": "true"},
        {"unknown": "field"},
        {"content": None, "attachments": [], "need_history": False},
    ],
)
def test_completion_request_rejects_invalid_shapes_and_boundaries(overrides):
    with pytest.raises(ValidationError):
        ConversationCompletionRequest(**_completion_payload(**overrides))


def test_completion_request_rejects_duplicate_attachments_after_normalization():
    attachment_id = str(uuid.uuid4())

    with pytest.raises(ValidationError, match="attachments must be unique"):
        ConversationCompletionRequest(**_completion_payload(attachments=[attachment_id, attachment_id]))


def test_update_request_accepts_title_or_strict_pin_and_rejects_empty_updates():
    assert ConversationUpdateRequest(title="Renamed").title == "Renamed"
    assert ConversationUpdateRequest(is_pinned=False).is_pinned is False

    for payload in [{}, {"title": None}, {"is_pinned": None}, {"title": ""}, {"title": "x" * 65}, {"is_pinned": "yes"}]:
        with pytest.raises(ValidationError):
            ConversationUpdateRequest(**payload)
