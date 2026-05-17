from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from agent.api.skills import router as skills_router
from agent.services.skills_auth_state import SkillsAuthState


pytestmark = pytest.mark.component


@dataclass
class FakeSkillsHubClient:
    calls: list[dict]

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
            return {
                "access_token": "token-1",
                "email": json_body["email"],
                "username": "crab",
                "role": "user",
            }
        if path == "/auth/me":
            assert token == "token-1"
            return {"email": "user@example.edu", "username": "crab"}
        raise AssertionError(f"Unexpected upstream request: {method} {path}")


def test_skills_auth_routes_store_login_token_and_forward_user_info(app_factory):
    app = app_factory()
    app.state.skills_hub_client = FakeSkillsHubClient(calls=[])
    app.state.skills_auth_state = SkillsAuthState()
    app.include_router(skills_router, prefix="/api")
    client = TestClient(app)

    login = client.post(
        "/api/auth/login",
        json={"email": "user@example.edu", "password": "secret"},
    )
    me = client.get("/api/auth/me")

    assert login.status_code == 200
    assert login.json()["access_token"] == "token-1"
    assert me.status_code == 200
    assert me.json() == {"email": "user@example.edu", "username": "crab"}
    assert app.state.skills_hub_client.calls[1]["token"] == "token-1"
