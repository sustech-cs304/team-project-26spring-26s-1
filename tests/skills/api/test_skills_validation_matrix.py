from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from agent.api.skills import router as skills_router
from agent.services.skills_auth_state import SkillsAuthState


pytestmark = pytest.mark.api


@dataclass
class RecordingSkillsClient:
    calls: list[dict] = field(default_factory=list)
    delete_submission_path: str = "/api/skills/{skill_id}/submission"
    login_payload: dict | None = None
    login_tokens: list[str] = field(default_factory=list)

    async def request_json(self, method, path, *, token=None, params=None, json_body=None):
        self.calls.append({"method": method, "path": path, "token": token, "params": params, "json_body": json_body})
        if path == "/auth/login":
            if self.login_payload is not None:
                return self.login_payload
            token = self.login_tokens.pop(0) if self.login_tokens else "token-1"
            return {"access_token": token, "email": json_body["email"], "username": "crab"}
        if path == "/auth/me":
            if token == "expired":
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="expired")
            return {"email": "user@example.edu"}
        return {"message": "ok", "params": params}

    async def request_text(self, *_args, **_kwargs):
        return "# Skill\n"

    async def post_multipart(self, path, *, token, fields, files):
        self.calls.append({"method": "POST", "path": path, "token": token, "fields": fields, "files": files})
        return {"message": "uploaded"}


class EmptyLocalStore:
    async def list_downloaded_skills(self):
        return []

    async def get_downloaded_skill_by_id(self, _skill_id):
        return None

    async def save_downloaded_skill(self, **_kwargs):
        return None

    async def uninstall_local_skill(self, _skill_id):
        return False


@pytest.fixture
def skills_validation_client(app_factory):
    client = RecordingSkillsClient()
    auth = SkillsAuthState()
    app = app_factory()
    app.state.skills_hub_client = client
    app.state.skills_auth_state = auth
    app.state.skills_local_store = EmptyLocalStore()
    app.include_router(skills_router, prefix="/api")
    return TestClient(app), client, auth


@pytest.mark.parametrize(
    ("url", "payload"),
    [
        ("/api/auth/register/captcha", {}),
        ("/api/auth/login", {"email": "user@example.edu"}),
        ("/api/auth/register", {"username": "crab", "email": "user@example.edu", "password": "secret"}),
    ],
)
def test_skills_auth_rejects_missing_required_fields(skills_validation_client, url, payload):
    client, _hub, _auth = skills_validation_client

    response = client.post(url, json=payload)

    assert response.status_code == 400


def test_skills_login_rejects_upstream_response_without_access_token(skills_validation_client):
    client, hub, _auth = skills_validation_client
    hub.login_payload = {"email": "user@example.edu"}

    response = client.post("/api/auth/login", json={"email": "user@example.edu", "password": "secret"})

    assert response.status_code == 502


@pytest.mark.parametrize(
    ("url", "payload"),
    [
        ("/api/auth/register/captcha", {"email": ""}),
        ("/api/auth/login", {"email": "", "password": "secret"}),
        ("/api/auth/login", {"email": "user@example.edu", "password": ""}),
        (
            "/api/auth/register",
            {"username": "", "email": "user@example.edu", "password": "secret", "verificationCode": "123456"},
        ),
    ],
)
@pytest.mark.xfail(strict=True, reason="Known issue: auth request models accept empty string fields.")
def test_skills_auth_should_reject_empty_string_fields(skills_validation_client, url, payload):
    client, _hub, _auth = skills_validation_client

    response = client.post(url, json=payload)

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("url", "payload"),
    [
        ("/api/auth/register/captcha", {"email": 123}),
        ("/api/auth/login", {"email": ["user@example.edu"], "password": "secret"}),
        (
            "/api/auth/register",
            {"username": "crab", "email": "user@example.edu", "password": {"raw": "secret"}, "verificationCode": "1"},
        ),
    ],
)
def test_skills_auth_rejects_wrong_field_types(skills_validation_client, url, payload):
    client, _hub, _auth = skills_validation_client

    response = client.post(url, json=payload)

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("url", "payload"),
    [
        ("/api/auth/register/captcha", {"email": None}),
        ("/api/auth/login", {"email": None, "password": "secret"}),
        ("/api/auth/login", {"email": "user@example.edu", "password": None}),
        (
            "/api/auth/register",
            {"username": None, "email": "user@example.edu", "password": "secret", "verificationCode": "123456"},
        ),
    ],
)
def test_skills_auth_rejects_null_required_fields(skills_validation_client, url, payload):
    client, _hub, _auth = skills_validation_client

    response = client.post(url, json=payload)

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("url", "payload"),
    [
        ("/api/auth/register/captcha", {"email": "not-an-email"}),
        ("/api/auth/login", {"email": "bad@", "password": "secret"}),
        (
            "/api/auth/register",
            {"username": "bad user", "email": "bad@", "password": "secret", "verificationCode": "123456"},
        ),
        (
            "/api/auth/register",
            {
                "username": "<script>alert(1)</script>",
                "email": "user@example.edu",
                "password": "secret",
                "verificationCode": "123456",
            },
        ),
        (
            "/api/auth/register",
            {
                "username": "' OR 1=1 --",
                "email": "user@example.edu",
                "password": "secret",
                "verificationCode": "123456",
            },
        ),
    ],
)
@pytest.mark.xfail(strict=True, reason="Known issue: auth request models do not validate email or username formats.")
def test_skills_auth_should_reject_invalid_format_and_security_strings(skills_validation_client, url, payload):
    client, _hub, _auth = skills_validation_client

    response = client.post(url, json=payload)

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("url", "payload"),
    [
        ("/api/auth/register/captcha", {"email": "user@example.edu", "role": "admin"}),
        ("/api/auth/login", {"email": "user@example.edu", "password": "secret", "role": "admin"}),
        (
            "/api/auth/register",
            {
                "username": "crab",
                "email": "user@example.edu",
                "password": "secret",
                "verificationCode": "123456",
                "role": "admin",
            },
        ),
    ],
)
@pytest.mark.xfail(strict=True, reason="Known issue: auth request models silently ignore unknown fields.")
def test_skills_auth_should_reject_unknown_fields(skills_validation_client, url, payload):
    client, _hub, _auth = skills_validation_client

    response = client.post(url, json=payload)

    assert response.status_code == 400


def test_skills_register_propagates_upstream_conflict(skills_validation_client):
    client, hub, _auth = skills_validation_client

    async def conflict(method, path, *, token=None, params=None, json_body=None):
        if path == "/auth/register":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already exists")
        return await RecordingSkillsClient().request_json(method, path, token=token, params=params, json_body=json_body)

    hub.request_json = conflict

    response = client.post(
        "/api/auth/register",
        json={
            "username": "crab",
            "email": "user@example.edu",
            "password": "secret",
            "verificationCode": "123456",
        },
    )

    assert response.status_code == 409


def test_skills_login_propagates_wrong_password_status(skills_validation_client):
    client, hub, _auth = skills_validation_client

    async def unauthorized(method, path, *, token=None, params=None, json_body=None):
        if path == "/auth/login":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
        return await RecordingSkillsClient().request_json(method, path, token=token, params=params, json_body=json_body)

    hub.request_json = unauthorized

    response = client.post("/api/auth/login", json={"email": "user@example.edu", "password": "wrong"})

    assert response.status_code == 401


def test_skills_auth_clears_token_after_upstream_401(skills_validation_client, run_async):
    client, _hub, auth = skills_validation_client
    run_async(auth.set_token("expired", user={"email": "user@example.edu"}))

    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert run_async(auth.get_snapshot()).access_token is None


def test_skills_repeated_login_overwrites_previous_token(skills_validation_client, run_async):
    client, hub, auth = skills_validation_client
    hub.login_tokens = ["token-1", "token-2"]

    first = client.post("/api/auth/login", json={"email": "user@example.edu", "password": "secret"})
    second = client.post("/api/auth/login", json={"email": "user@example.edu", "password": "secret"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert run_async(auth.get_snapshot()).access_token == "token-2"


@pytest.mark.parametrize(
    ("params", "expected_status"),
    [
        ({"page": 0}, 400),
        ({"page_size": 0}, 400),
        ({"page_size": 101}, 400),
        ({"page": 1, "page_size": 100, "search": "  writer  "}, 200),
        ({"tag_id": -1}, 200),
    ],
)
def test_skills_list_validates_pagination_and_records_current_tag_id_behavior(
    skills_validation_client,
    params,
    expected_status,
):
    client, hub, _auth = skills_validation_client

    response = client.get("/api/skills", params=params)

    assert response.status_code == expected_status
    if expected_status == 200 and "search" in params:
        assert hub.calls[-1]["params"]["search"] == "writer"


@pytest.mark.parametrize(
    "params",
    [
        {"page": "abc"},
        {"page": ""},
        {"page_size": "abc"},
        {"page_size": ""},
        {"tag_id": "abc"},
        {"page": 1.5},
        {"page_size": 1.5},
    ],
)
def test_skills_list_rejects_query_type_and_format_errors(skills_validation_client, params):
    client, _hub, _auth = skills_validation_client

    response = client.get("/api/skills", params=params)

    assert response.status_code == 400


@pytest.mark.parametrize(
    "search",
    [
        "x" * 4096,
        "{\"$ne\": null}",
        "admin\x00name",
        "$(touch /tmp/pwned)",
        "{{7*7}}",
    ],
)
@pytest.mark.xfail(strict=True, reason="Known issue: skills search accepts unbounded fuzzy/security payloads.")
def test_skills_list_should_reject_unsafe_or_extreme_search_values(skills_validation_client, search):
    client, _hub, _auth = skills_validation_client

    response = client.get("/api/skills", params={"search": search})

    assert response.status_code == 400


@pytest.mark.xfail(strict=True, reason="Known issue: skills list does not reject negative tag_id.")
def test_skills_list_should_reject_negative_tag_id(skills_validation_client):
    client, _hub, _auth = skills_validation_client

    response = client.get("/api/skills", params={"tag_id": -1})

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("GET", "/api/skills/-1"),
        ("GET", "/api/skills/-1/download"),
        ("DELETE", "/api/skill/-1/delete"),
        ("POST", "/api/skill/-1/uninstall"),
    ],
)
@pytest.mark.xfail(strict=True, reason="Known issue: skill path ids accept negative integers.")
def test_skills_routes_should_reject_negative_skill_ids(skills_validation_client, method, url):
    client, _hub, _auth = skills_validation_client
    client.post("/api/auth/login", json={"email": "user@example.edu", "password": "secret"})

    response = client.request(method, url)

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("GET", "/api/skills/not-an-int"),
        ("GET", "/api/skills/not-an-int/download"),
        ("GET", "/api/skills/downloaded/not-an-int"),
        ("DELETE", "/api/skill/not-an-int/delete"),
        ("POST", "/api/skill/not-an-int/uninstall"),
    ],
)
def test_skills_routes_reject_non_integer_skill_ids(skills_validation_client, method, url):
    client, _hub, _auth = skills_validation_client
    client.post("/api/auth/login", json={"email": "user@example.edu", "password": "secret"})

    response = client.request(method, url)

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("GET", "/api/skills/999"),
        ("GET", "/api/skills/999/download"),
        ("DELETE", "/api/skill/999/delete"),
    ],
)
def test_skills_cloud_routes_propagate_upstream_not_found(skills_validation_client, method, url):
    client, hub, _auth = skills_validation_client
    client.post("/api/auth/login", json={"email": "user@example.edu", "password": "secret"})

    async def not_found(request_method, path, *, token=None, params=None, json_body=None):
        if "999" in path:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
        return await RecordingSkillsClient().request_json(
            request_method,
            path,
            token=token,
            params=params,
            json_body=json_body,
        )

    async def not_found_text(request_method, path, *, token=None, params=None):
        if "999" in path:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
        return "# Skill\n"

    hub.request_json = not_found
    hub.request_text = not_found_text

    response = client.request(method, url)

    assert response.status_code == 404


def test_skills_search_injection_is_forwarded_as_trimmed_data(skills_validation_client):
    client, hub, _auth = skills_validation_client
    payload = "  <script>alert(1)</script>' OR 1=1 --  "

    response = client.get("/api/skills", params={"search": payload})

    assert response.status_code == 200
    assert hub.calls[-1]["params"]["search"] == payload.strip()


@pytest.mark.parametrize("url", ["/api/auth/me", "/api/skills/me", "/api/skills", "/api/skill/7/delete"])
def test_skills_authenticated_routes_reject_missing_login(skills_validation_client, url):
    client, _hub, _auth = skills_validation_client

    if url == "/api/skills":
        response = client.post(url, files={"file": ("skill.md", b"# Skill", "text/markdown")})
    elif url.endswith("/delete"):
        response = client.delete(url)
    else:
        response = client.get(url)

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("files", "tag_ids"),
    [
        ({"file": ("skill.md", b"# Skill", "text/markdown")}, None),
        ({"file": ("skill.md", b"# Skill", "text/markdown")}, "1,2"),
        ({"file": ("../skill.md", b"# Skill", "text/markdown")}, "1;DROP TABLE tags"),
    ],
)
def test_skills_upload_currently_forwards_positive_and_unsafe_multipart_inputs(
    skills_validation_client,
    files,
    tag_ids,
):
    client, hub, _auth = skills_validation_client
    client.post("/api/auth/login", json={"email": "user@example.edu", "password": "secret"})
    data = {} if tag_ids is None else {"tag_ids": tag_ids}

    response = client.post("/api/skills", files=files, data=data)

    assert response.status_code == 200
    assert hub.calls[-1]["files"]["file"][0] == files["file"][0]


def test_skills_upload_rejects_missing_file_multipart_field(skills_validation_client):
    client, _hub, _auth = skills_validation_client
    client.post("/api/auth/login", json={"email": "user@example.edu", "password": "secret"})

    response = client.post("/api/skills", data={"tag_ids": "1,2"})

    assert response.status_code == 400


@pytest.mark.parametrize("tag_ids", ["", "   ", "1", "1,2", "999999999999999999999"])
def test_skills_upload_forwards_supported_tag_id_form_values(skills_validation_client, tag_ids):
    client, hub, _auth = skills_validation_client
    client.post("/api/auth/login", json={"email": "user@example.edu", "password": "secret"})

    response = client.post(
        "/api/skills",
        files={"file": ("skill.md", b"# Skill", "text/markdown")},
        data={"tag_ids": tag_ids},
    )

    assert response.status_code == 200
    if tag_ids.strip():
        assert hub.calls[-1]["fields"]["tag_ids"] == tag_ids.strip()
    else:
        assert hub.calls[-1]["fields"] == {}


@pytest.mark.xfail(strict=True, reason="Known issue: uninstall returns 200 instead of 404 for unknown local skills.")
def test_skills_uninstall_should_return_404_for_not_installed_skill(skills_validation_client):
    client, _hub, _auth = skills_validation_client

    response = client.post("/api/skill/404/uninstall")

    assert response.status_code == 404


@pytest.mark.xfail(strict=True, reason="Known issue: skills upload forwards unsafe filenames and tag_ids without local validation.")
def test_skills_upload_should_reject_unsafe_filename_and_tag_ids(skills_validation_client):
    client, _hub, _auth = skills_validation_client
    client.post("/api/auth/login", json={"email": "user@example.edu", "password": "secret"})

    response = client.post(
        "/api/skills",
        files={"file": ("../skill.md", b"# Skill", "text/markdown")},
        data={"tag_ids": "1;DROP TABLE tags"},
    )

    assert response.status_code == 400


@pytest.mark.xfail(strict=True, reason="Known issue: empty skill uploads are forwarded to upstream.")
def test_skills_upload_should_reject_empty_file(skills_validation_client):
    client, _hub, _auth = skills_validation_client
    client.post("/api/auth/login", json={"email": "user@example.edu", "password": "secret"})

    response = client.post(
        "/api/skills",
        files={"file": ("skill.md", b"", "text/markdown")},
        data={"tag_ids": "1"},
    )

    assert response.status_code == 400
