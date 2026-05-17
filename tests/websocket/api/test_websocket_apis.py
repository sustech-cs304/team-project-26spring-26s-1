from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import agent.api.conversation as conversation_api
from agent.api.conversation import router as conversation_router
from agent.im.onebot.router import router as onebot_router


pytestmark = pytest.mark.api


class FakeOneBotHub:
    async def serve(self, websocket):
        await websocket.accept()
        await websocket.send_json({"status": "connected"})
        await websocket.close()


def test_onebot_reverse_websocket_delegates_to_hub(app_factory):
    app = app_factory()
    app.state.OneBotHub = FakeOneBotHub()
    app.include_router(onebot_router, prefix="/api")
    client = TestClient(app)

    with client.websocket_connect("/api/onebot/ws") as websocket:
        assert websocket.receive_json() == {"status": "connected"}


class FakeAsrWebSocket:
    def __init__(self, responses=None):
        self._returned = False
        self._responses = list(['{"text":"recognized"}'] if responses is None else responses)
        self.sent: list[str | bytes] = []
        self.closed = False

    async def send(self, data):
        self.sent.append(data)

    async def recv(self):
        if self._responses:
            return self._responses.pop(0)
        raise RuntimeError("fake upstream closed")

    async def close(self):
        self.closed = True
        return None


class FakeAsrConnect:
    def __init__(self, upstream):
        self.upstream = upstream
        self.calls: list[dict] = []

    async def __call__(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return self.upstream


async def fake_connect(*_args, **_kwargs):
    return FakeAsrWebSocket()


def test_conversation_asr_websocket_proxies_upstream_text(app_factory, monkeypatch):
    monkeypatch.setattr(conversation_api.websockets, "connect", fake_connect)
    app = app_factory()
    app.include_router(conversation_router, prefix="/api")
    client = TestClient(app)

    with client.websocket_connect("/api/conversation/asr") as websocket:
        websocket.send_text("audio-chunk")
        assert websocket.receive_text() == '{"text":"recognized"}'


def test_conversation_asr_websocket_forwards_binary_payloads(app_factory, monkeypatch):
    upstream = FakeAsrWebSocket(responses=['{"text":"from-bytes"}'])
    fake_connect = FakeAsrConnect(upstream)
    monkeypatch.setattr(conversation_api.websockets, "connect", fake_connect)
    app = app_factory()
    app.include_router(conversation_router, prefix="/api")
    client = TestClient(app)

    with client.websocket_connect("/api/conversation/asr") as websocket:
        websocket.send_bytes(b"\x00\x01audio")
        assert websocket.receive_text() == '{"text":"from-bytes"}'

    assert upstream.sent == [b"\x00\x01audio"]
    assert upstream.closed is True
    assert fake_connect.calls[0]["kwargs"]["max_size"] is None


@pytest.mark.parametrize(
    ("payload", "send_method", "expected_sent", "upstream_response"),
    [
        ("", "send_text", "", '{"text":"empty-text"}'),
        ("A" * 65536, "send_text", "A" * 65536, '{"text":"long-text"}'),
        (b"", "send_bytes", b"", '{"text":"empty-bytes"}'),
        (b"\x00\x01" * 32768, "send_bytes", b"\x00\x01" * 32768, '{"text":"long-bytes"}'),
    ],
    ids=["empty-text", "long-text", "empty-bytes", "long-bytes"],
)
def test_conversation_asr_websocket_forwards_boundary_payloads(
    app_factory,
    monkeypatch,
    payload,
    send_method,
    expected_sent,
    upstream_response,
):
    upstream = FakeAsrWebSocket(responses=[upstream_response])
    monkeypatch.setattr(conversation_api.websockets, "connect", FakeAsrConnect(upstream))
    app = app_factory()
    app.include_router(conversation_router, prefix="/api")
    client = TestClient(app)

    with client.websocket_connect("/api/conversation/asr") as websocket:
        getattr(websocket, send_method)(payload)
        assert websocket.receive_text() == upstream_response

    assert upstream.sent == [expected_sent]
    assert upstream.closed is True


def test_conversation_asr_websocket_returns_error_when_upstream_recv_fails(app_factory, monkeypatch):
    upstream = FakeAsrWebSocket(responses=[])
    monkeypatch.setattr(conversation_api.websockets, "connect", FakeAsrConnect(upstream))
    app = app_factory()
    app.include_router(conversation_router, prefix="/api")
    client = TestClient(app)

    with client.websocket_connect("/api/conversation/asr") as websocket:
        error = websocket.receive_json()

    assert error == {"error": "fake upstream closed"}
    assert upstream.closed is True


async def fake_connect_failure(*_args, **_kwargs):
    raise RuntimeError("upstream unavailable")


def test_conversation_asr_websocket_reports_upstream_connect_failure(app_factory, monkeypatch):
    monkeypatch.setattr(conversation_api.websockets, "connect", fake_connect_failure)
    app = app_factory()
    app.include_router(conversation_router, prefix="/api")
    client = TestClient(app)

    with client.websocket_connect("/api/conversation/asr") as websocket:
        assert websocket.receive_json() == {"error": "upstream unavailable"}


def test_conversation_asr_websocket_reports_invalid_upstream_binary(app_factory, monkeypatch):
    upstream = FakeAsrWebSocket(responses=[b"\xff\xfe"])
    monkeypatch.setattr(conversation_api.websockets, "connect", FakeAsrConnect(upstream))
    app = app_factory()
    app.include_router(conversation_router, prefix="/api")
    client = TestClient(app)

    with client.websocket_connect("/api/conversation/asr") as websocket:
        error = websocket.receive_json()

    assert "utf-8" in error["error"].lower()
    assert upstream.closed is True
