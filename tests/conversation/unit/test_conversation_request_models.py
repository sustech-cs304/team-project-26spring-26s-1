from __future__ import annotations

import uuid

import pytest

from agent.api.conversation import ConversationCompletionRequest, ConversationUpdateRequest


pytestmark = pytest.mark.unit


def _completion_payload(**overrides):
    payload = {
        "conversation_id": str(uuid.uuid4()),
        "request_id": str(uuid.uuid4()),
        "content": "hello",
        "created_at": 1,
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
def test_completion_request_currently_accepts_unconstrained_shapes_and_boundaries(overrides):
    request = ConversationCompletionRequest(**_completion_payload(**overrides))

    for key, value in overrides.items():
        if key == "unknown":
            assert not hasattr(request, key)
        elif key == "need_history" and value == "true":
            assert request.need_history is True
        else:
            assert getattr(request, key) == value


def test_completion_request_preserves_duplicate_attachments():
    attachment_id = str(uuid.uuid4())

    request = ConversationCompletionRequest(**_completion_payload(attachments=[attachment_id, attachment_id]))

    assert request.attachments == [attachment_id, attachment_id]


def test_update_request_accepts_current_title_and_pin_shapes():
    assert ConversationUpdateRequest(title="Renamed").title == "Renamed"
    assert ConversationUpdateRequest(is_pinned=False).is_pinned is False

    assert ConversationUpdateRequest().model_dump() == {"title": None, "is_pinned": None}
    assert ConversationUpdateRequest(title=None).title is None
    assert ConversationUpdateRequest(is_pinned=None).is_pinned is None
    assert ConversationUpdateRequest(title="").title == ""
    assert ConversationUpdateRequest(title="x" * 65).title == "x" * 65
    assert ConversationUpdateRequest(is_pinned="yes").is_pinned is True
