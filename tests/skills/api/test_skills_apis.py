from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from agent.api.skills import router as skills_router
from agent.services.skills_auth_state import SkillsAuthState


pytestmark = pytest.mark.api


@dataclass
class LocalSkillRow:
    cloud_skill_id: int
    name: str
    description: str
    markdown_path: str


@dataclass
class FakeSkillsHubClient:
    calls: list[dict] = field(default_factory=list)

    async def request_json(self, method, path, *, token=None, params=None, json_body=None):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "token": token,
                "params": params,
                "json_body": json_body,
            }
        )
        if path == "/auth/login":
            return {"access_token": "token-1", "email": json_body["email"], "username": "crab"}
        if path == "/auth/register/captcha":
            return {"message": "sent"}
        if path == "/auth/register":
            return {"message": "registered"}
        if path == "/api/skills":
            return {"items": [{"id": 1, "name": "Summarizer"}], "total": 1}
        if path == "/api/skills/me":
            assert token == "token-1"
            return {"items": [{"id": 2, "name": "Mine"}], "total": 1}
        if path == "/api/skills/7":
            return {"id": 7, "name": "Writer", "description": "Writes"}
        if path == "/api/tags":
            return [{"id": 1, "name": "productivity"}]
        if path == "/api/skills/7/submission":
            assert token == "token-1"
            return {"message": "deleted"}
        raise AssertionError(f"Unexpected request_json call: {method} {path}")

    async def request_text(self, method, path, *, token=None, params=None):
        self.calls.append({"method": method, "path": path, "token": token, "params": params})
        if path == "/api/skills/7/download":
            return "# Writer\n"
        raise AssertionError(f"Unexpected request_text call: {method} {path}")

    async def post_multipart(self, path, *, token, fields, files):
        self.calls.append(
            {
                "method": "POST",
                "path": path,
                "token": token,
                "fields": fields,
                "files": {key: value[:2] for key, value in files.items()},
            }
        )
        return {"id": 9, "message": "uploaded"}


class FakeSkillsLocalStore:
    def __init__(self, tmp_path: Path):
        self.tmp_path = tmp_path
        self.markdown_path = tmp_path / "skill.md"
        self.markdown_path.write_text("# Local skill\n", encoding="utf-8")
        self.saved: list[dict] = []
        self.uninstalled: list[int] = []

    async def list_downloaded_skills(self):
        return [
            LocalSkillRow(
                cloud_skill_id=7,
                name="Writer",
                description="Writes",
                markdown_path=str(self.markdown_path),
            )
        ]

    async def get_downloaded_skill_by_id(self, skill_id: int):
        if skill_id == 7:
            return LocalSkillRow(
                cloud_skill_id=7,
                name="Writer",
                description="Writes",
                markdown_path=str(self.markdown_path),
            )
        return None

    async def save_downloaded_skill(self, **kwargs):
        self.saved.append(kwargs)

    async def uninstall_local_skill(self, skill_id: int):
        self.uninstalled.append(skill_id)
        return skill_id == 7


def _build_app(app_factory, tmp_path):
    app = app_factory()
    app.state.skills_hub_client = FakeSkillsHubClient()
    app.state.skills_auth_state = SkillsAuthState()
    app.state.skills_local_store = FakeSkillsLocalStore(tmp_path)
    app.include_router(skills_router, prefix="/api")
    return app


def _login(client: TestClient):
    response = client.post(
        "/api/auth/login",
        json={"email": "user@example.edu", "password": "secret"},
    )
    assert response.status_code == 200


def test_skills_public_and_authenticated_proxy_routes(app_factory, tmp_path):
    app = _build_app(app_factory, tmp_path)
    client = TestClient(app)

    captcha = client.post("/api/auth/register/captcha", json={"email": "user@example.edu"})
    register = client.post(
        "/api/auth/register",
        json={
            "username": "crab",
            "email": "user@example.edu",
            "password": "secret",
            "verificationCode": "123456",
        },
    )
    skills = client.get("/api/skills", params={"page": 2, "page_size": 5, "search": " writer "})
    tags = client.get("/api/tags")
    unauthorized = client.get("/api/skills/me")

    _login(client)
    mine = client.get("/api/skills/me")
    detail = client.get("/api/skills/7")
    deleted = client.delete("/api/skill/7/delete")

    assert captcha.json() == {"message": "sent"}
    assert register.json() == {"message": "registered"}
    assert skills.json()["items"][0]["name"] == "Summarizer"
    assert tags.json()[0]["name"] == "productivity"
    assert unauthorized.status_code == 401
    assert mine.status_code == 200
    assert mine.json()["items"][0]["name"] == "Mine"
    assert detail.json()["name"] == "Writer"
    assert deleted.json() == {"message": "deleted"}


def test_skills_download_upload_local_detail_and_uninstall_routes(app_factory, tmp_path):
    app = _build_app(app_factory, tmp_path)
    client = TestClient(app)

    downloaded = client.get("/api/skills/downloaded")
    downloaded_detail = client.get("/api/skills/downloaded/7")
    missing_detail = client.get("/api/skills/downloaded/8")
    download = client.get("/api/skills/7/download")
    unauth_upload = client.post(
        "/api/skills",
        data={"tag_ids": "1,2"},
        files={"file": ("skill.md", b"# Skill", "text/markdown")},
    )
    _login(client)
    upload = client.post(
        "/api/skills",
        data={"tag_ids": "1,2"},
        files={"file": ("skill.md", b"# Skill", "text/markdown")},
    )
    uninstall = client.post("/api/skill/7/uninstall")
    uninstall_missing = client.post("/api/skill/404/uninstall")

    assert downloaded.status_code == 200
    assert downloaded.json()[0]["cloud_skill_id"] == 7
    assert downloaded_detail.status_code == 200
    assert downloaded_detail.json()["markdown_content"] == "# Local skill\n"
    assert missing_detail.status_code == 404
    assert download.status_code == 200
    assert app.state.skills_local_store.saved[0]["markdown_content"] == "# Writer\n"
    assert unauth_upload.status_code == 401
    assert upload.status_code == 200
    assert upload.json()["message"] == "uploaded"
    assert uninstall.json() == {"message": "卸载成功"}
    assert uninstall_missing.json() == {"message": "技能未安装"}


def test_downloaded_skill_detail_returns_404_when_markdown_file_is_missing(app_factory, tmp_path):
    app = _build_app(app_factory, tmp_path)
    Path(app.state.skills_local_store.markdown_path).unlink()
    client = TestClient(app)

    response = client.get("/api/skills/downloaded/7")

    assert response.status_code == 404


@pytest.mark.xfail(strict=True, reason="Known issue: downloaded skill detail reads arbitrary local markdown_path values.")
def test_downloaded_skill_detail_should_reject_local_path_traversal_row(app_factory, tmp_path):
    app = _build_app(app_factory, tmp_path)
    outside = tmp_path / "outside-secret.md"
    outside.write_text("# secret\n", encoding="utf-8")
    app.state.skills_local_store.markdown_path = outside
    client = TestClient(app)

    response = client.get("/api/skills/downloaded/7")

    assert response.status_code == 400


def test_download_skill_rejects_malformed_upstream_detail(app_factory, tmp_path):
    app = _build_app(app_factory, tmp_path)

    async def malformed_detail(method, path, *, token=None, params=None, json_body=None):
        if path == "/api/skills/7":
            return ["not", "an", "object"]
        return await FakeSkillsHubClient().request_json(method, path, token=token, params=params, json_body=json_body)

    app.state.skills_hub_client.request_json = malformed_detail
    client = TestClient(app)

    response = client.get("/api/skills/7/download")

    assert response.status_code == 502


def test_delete_submission_route_reports_not_configured(app_factory, tmp_path):
    app = _build_app(app_factory, tmp_path)
    client = TestClient(app)
    _login(client)

    response = client.delete("/api/skill/7/delete")

    assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
