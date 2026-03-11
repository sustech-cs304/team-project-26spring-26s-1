from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

# -----------------------------
# Test DB bootstrap
# -----------------------------
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "test_api_full_flow.db"

if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["API_DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_api_full_flow.db"
os.environ["API_RELOAD"] = "false"

# Import after env is set.
from api.app import create_app  # noqa: E402


def _query_one(sql: str, params: tuple = ()) -> tuple | None:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        conn.close()


def _query_all(sql: str, params: tuple = ()) -> list[tuple]:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run() -> None:
    app = create_app()

    with TestClient(app) as client:
        # 1) POST /conversation
        resp = client.post("/conversation")
        _assert(resp.status_code == 200, f"/conversation failed: {resp.status_code} {resp.text}")
        conv = resp.json()
        conversation_id = conv["conversation_id"]

        # DB assertion: conversation inserted.
        row = _query_one(
            "SELECT conversation_id, title, is_active, is_pinned FROM conversations WHERE conversation_id = ?",
            (conversation_id,),
        )
        _assert(row is not None, "conversation not inserted into DB")

        # 2) GET /conversations/
        resp = client.get("/conversations/", params={"page": 1, "pageSize": 25})
        _assert(resp.status_code == 200, f"/conversations/ failed: {resp.status_code} {resp.text}")
        listed = resp.json().get("conversations", [])
        _assert(any(item["conversation_id"] == conversation_id for item in listed), "conversation not in list")

        # 3) GET /conversations/search
        resp = client.get(
            "/conversations/search",
            params={"keywords": "新对话", "page": 1, "pageSize": 25},
        )
        _assert(resp.status_code == 200, f"/conversations/search failed: {resp.status_code} {resp.text}")

        # 4) PATCH /conversation/{conversation_id}
        new_title = "测试会话标题"
        resp = client.patch(
            f"/conversation/{conversation_id}",
            data={"title": new_title, "is_pinned": "true"},
        )
        _assert(resp.status_code == 200, f"patch conversation failed: {resp.status_code} {resp.text}")

        row = _query_one(
            "SELECT title, is_pinned FROM conversations WHERE conversation_id = ?",
            (conversation_id,),
        )
        _assert(row == (new_title, 1), "conversation patch not persisted")

        # 5) POST /conversation/completion (SSE)
        request_id = "req-test-001"
        form = {
            "conversation_id": conversation_id,
            "request_id": request_id,
            "content": "你好，请简单介绍一下你自己。",
            "create_at": str(int(time.time() * 1000)),
            "need_history": "false",
        }

        sse_lines: list[str] = []
        with client.stream("POST", "/conversation/completion", data=form) as stream_resp:
            _assert(stream_resp.status_code == 200, f"completion failed: {stream_resp.status_code}")
            for line in stream_resp.iter_lines():
                if line:
                    sse_lines.append(line)

        sse_text = "\n".join(sse_lines)
        _assert("event: history" in sse_text, "completion stream missing history event")
        _assert("event: set_title" in sse_text, "completion stream missing set_title event")
        _assert("event: done" in sse_text, "completion stream missing done event")

        # DB assertion: user message written during completion pre-stream stage.
        msg_row = _query_one(
            "SELECT message_id, role, content, status FROM messages WHERE conversation_id = ? ORDER BY seq DESC LIMIT 1",
            (conversation_id,),
        )
        _assert(msg_row is not None, "message not inserted into DB during completion")
        message_id = msg_row[0]
        _assert(msg_row[1] == "user", f"unexpected message role: {msg_row[1]}")

        # 6) POST /conversation/cancelchat
        resp = client.post(
            "/conversation/cancelchat",
            params={"conversation_id": conversation_id, "message_id": message_id},
        )
        _assert(resp.status_code == 200, f"cancel failed: {resp.status_code} {resp.text}")

        row = _query_one(
            "SELECT status FROM messages WHERE message_id = ?",
            (message_id,),
        )
        _assert(row is not None and row[0] == "error", "cancel status not persisted on message")

        row = _query_one(
            "SELECT is_active FROM conversations WHERE conversation_id = ?",
            (conversation_id,),
        )
        _assert(row is not None and row[0] == 0, "cancel status not persisted on conversation")

        # 7) GET /chat/icebreakers (current framework behavior: 501 Not Implemented)
        resp = client.get("/chat/icebreakers")
        _assert(resp.status_code == 501, f"icebreakers failed: {resp.status_code} {resp.text}")

        # 8) DELETE /conversation/{conversation_id}
        resp = client.delete(f"/conversation/{conversation_id}")
        _assert(resp.status_code == 200, f"delete conversation failed: {resp.status_code} {resp.text}")

        remaining = _query_all(
            "SELECT conversation_id FROM conversations WHERE conversation_id = ?",
            (conversation_id,),
        )
        _assert(len(remaining) == 0, "conversation was not deleted")

    print("✅ 全流程测试通过：接口 -> 缓冲 -> 入库 -> 状态变更 -> 删除")


if __name__ == "__main__":
    run()
