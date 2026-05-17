from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from agent.api.config import router as config_router
from agent.config import AppConfig, get_config


pytestmark = pytest.mark.scenario


@dataclass
class ScenarioConfigManager:
    patches: list[dict] = field(default_factory=list)
    current: AppConfig = field(default_factory=get_config)

    async def patch(self, delta):
        self.patches.append(dict(delta))
        merged = self.current.model_dump()
        for section, values in delta.items():
            if isinstance(values, dict) and isinstance(merged.get(section), dict):
                merged[section].update(values)
            else:
                merged[section] = values
        self.current = AppConfig.model_validate(merged)
        return self.current


def test_config_patch_then_get_scenario_keeps_patch_payload_scoped(app_factory):
    manager = ScenarioConfigManager()
    app = app_factory()
    app.state.ConfigManager = manager
    app.include_router(config_router, prefix="/api")
    client = TestClient(app)

    before = client.get("/api/get_config")
    patched = client.patch(
        "/api/patch_config",
        json={"notification": {"enabled": False, "app_name": "Scenario Crab"}},
    )
    second_patch = client.patch(
        "/api/patch_config",
        json={"websearch": {"base_url": "http://scenario.local"}},
    )

    assert before.status_code == 200
    assert patched.status_code == 200
    assert patched.json()["notification"]["app_name"] == "Scenario Crab"
    assert patched.json()["notification"]["enabled"] is False
    assert second_patch.status_code == 200
    assert second_patch.json()["notification"]["app_name"] == "Scenario Crab"
    assert second_patch.json()["websearch"]["base_url"] == "http://scenario.local"
    assert manager.patches == [
        {"notification": {"enabled": False, "app_name": "Scenario Crab"}},
        {"websearch": {"base_url": "http://scenario.local"}},
    ]


@pytest.mark.xfail(strict=True, reason="Known issue: get_config exposes configured API keys in the response body.")
def test_config_get_scenario_should_not_expose_secrets(app_factory):
    app = app_factory()
    app.include_router(config_router, prefix="/api")
    client = TestClient(app)

    response = client.get("/api/get_config")

    assert response.status_code == 200
    assert "api_key" not in str(response.json())
