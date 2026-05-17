from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agent.api.config import router as config_router
from agent.config import AppConfig, build_patched_config, get_config


pytestmark = pytest.mark.api


@dataclass
class FakeConfigManager:
    patched: list[dict] = field(default_factory=list)

    async def patch(self, delta):
        self.patched.append(dict(delta))
        if delta.get("invalid"):
            raise ValidationError.from_exception_data(
                "AppConfig",
                [
                    {
                        "type": "literal_error",
                        "loc": ("api", "agent", "type"),
                        "msg": "Input should be 'OpenAI', 'Qwen' or 'Anthropic'",
                        "input": "BadProvider",
                        "ctx": {"expected": "'OpenAI', 'Qwen' or 'Anthropic'"},
                    }
                ],
            )
        config = get_config()
        if "notification" in delta:
            merged = config.model_dump()
            merged["notification"].update(delta["notification"])
            return AppConfig.model_validate(merged)
        return config


class RaisingConfigManager:
    async def patch(self, _delta):
        raise RuntimeError("config backend failed")


class ValidatingConfigManager:
    async def patch(self, delta):
        return build_patched_config(delta, base_config=get_config())


def test_config_api_returns_config_and_maps_validation_error_to_400(app_factory):
    manager = FakeConfigManager()
    app = app_factory()
    app.state.ConfigManager = manager
    app.include_router(config_router, prefix="/api")
    client = TestClient(app)

    get_response = client.get("/api/get_config")
    patch_response = client.patch(
        "/api/patch_config",
        json={"notification": {"enabled": False, "app_name": "Test Crab"}},
    )
    bad_response = client.patch("/api/patch_config", json={"invalid": True})

    assert get_response.status_code == 200
    assert "api" in get_response.json()
    assert patch_response.status_code == 200
    assert patch_response.json()["notification"]["app_name"] == "Test Crab"
    assert manager.patched[0] == {"notification": {"enabled": False, "app_name": "Test Crab"}}
    assert bad_response.status_code == 400
    assert "api.agent.type" in bad_response.json()["message"]


@pytest.mark.parametrize("payload", [[], "not-an-object", 1, None])
def test_config_patch_rejects_non_object_body(app_factory, payload):
    manager = FakeConfigManager()
    app = app_factory()
    app.state.ConfigManager = manager
    app.include_router(config_router, prefix="/api")
    client = TestClient(app)

    response = client.patch("/api/patch_config", json=payload)

    assert response.status_code == 400
    assert manager.patched == []


def test_config_patch_rejects_missing_body(app_factory):
    manager = FakeConfigManager()
    app = app_factory()
    app.state.ConfigManager = manager
    app.include_router(config_router, prefix="/api")
    client = TestClient(app)

    response = client.patch("/api/patch_config")

    assert response.status_code == 400
    assert manager.patched == []


@pytest.mark.parametrize(
    "payload",
    [
        {"notification": {"enabled": False}},
        {"notification": {"enabled": True, "app_name": "x" * 256}},
        {"notification": {"enabled": False, "app_name": "<script>alert(1)</script>"}},
        {"notification": {"enabled": False, "app_name": "' OR 1=1 --"}},
        {"notification": {"enabled": False, "app_name": "$(touch /tmp/pwned)"}},
        {"notification": {"enabled": False, "app_name": "{\"$ne\": null}"}},
    ],
)
def test_config_patch_accepts_spec_object_and_treats_security_strings_as_data(app_factory, payload):
    manager = FakeConfigManager()
    app = app_factory()
    app.state.ConfigManager = manager
    app.include_router(config_router, prefix="/api")
    client = TestClient(app)

    response = client.patch("/api/patch_config", json=payload)

    assert response.status_code == 200
    assert manager.patched[-1] == payload


@pytest.mark.xfail(strict=True, reason="Known issue: config patch currently allows unknown top-level keys through the API boundary.")
def test_config_patch_should_reject_unknown_top_level_keys(app_factory):
    manager = FakeConfigManager()
    app = app_factory()
    app.state.ConfigManager = manager
    app.include_router(config_router, prefix="/api")
    client = TestClient(app)

    response = client.patch("/api/patch_config", json={"unknown": {"enabled": True}})

    assert response.status_code == 400


def test_config_patch_rejects_deep_invalid_provider_type(app_factory):
    manager = FakeConfigManager()
    app = app_factory()
    app.state.ConfigManager = manager
    app.include_router(config_router, prefix="/api")
    client = TestClient(app)

    response = client.patch("/api/patch_config", json={"invalid": True})

    assert response.status_code == 400
    assert response.json()["message"].startswith("api.agent.type:")


@pytest.mark.parametrize(
    "payload",
    [
        {"api": {"agent": {"max_token_count": 0}}},
        {"code_interpreter": {"default_timeout_s": 0}},
        {"code_interpreter": {"auto_approve_max_risk_level": "Extreme"}},
    ],
)
def test_config_patch_rejects_constraints_documented_from_app_config(app_factory, payload):
    app = app_factory()
    app.state.ConfigManager = ValidatingConfigManager()
    app.include_router(config_router, prefix="/api")
    client = TestClient(app)

    response = client.patch("/api/patch_config", json=payload)

    assert response.status_code == 400


def test_config_patch_returns_500_when_manager_raises_unexpected_error(app_factory):
    app = app_factory()
    app.state.ConfigManager = RaisingConfigManager()
    app.include_router(config_router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.patch("/api/patch_config", json={"notification": {"enabled": False}})

    assert response.status_code == 500


@pytest.mark.xfail(strict=True, reason="Known issue: config API returns a generic 500 when ConfigManager is missing.")
def test_config_patch_should_report_manager_missing_as_503(app_factory):
    app = app_factory()
    app.include_router(config_router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.patch("/api/patch_config", json={"notification": {"enabled": False}})

    assert response.status_code == 503


@pytest.mark.xfail(strict=True, reason="Known issue: get_config exposes configured API keys in the response body.")
def test_config_get_should_not_expose_api_keys(app_factory):
    app = app_factory()
    app.include_router(config_router, prefix="/api")
    client = TestClient(app)

    response = client.get("/api/get_config")

    assert response.status_code == 200
    assert "api_key" not in str(response.json())
