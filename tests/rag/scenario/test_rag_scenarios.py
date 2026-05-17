from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent.api.rag import router as rag_router


pytestmark = pytest.mark.scenario


class ScenarioRagCloudSyncService:
    def __init__(self):
        self.trigger_count = 0
        self.status = {
            "status": "idle",
            "stage": "idle",
            "progress": 0,
            "message": "idle",
            "knowledge_base_id": "default",
            "version": None,
            "downloaded_files": [],
            "embedded_added": 0,
            "embedded_overwritten": 0,
            "embedded_failed": 0,
            "error": None,
        }

    async def trigger_sync(self):
        self.trigger_count += 1
        self.status = {
            **self.status,
            "status": "running",
            "stage": "download",
            "progress": 25,
            "message": "Downloading files",
            "downloaded_files": ["course.md"],
        }
        return self.status

    def get_status(self):
        return self.status


def test_rag_sync_trigger_to_status_progress_scenario(app_factory):
    service = ScenarioRagCloudSyncService()
    app = app_factory()
    app.state.rag_cloud_sync_service = service
    app.include_router(rag_router, prefix="/api")
    client = TestClient(app)

    before = client.get("/api/rag/sync/status")
    triggered = client.post("/api/rag/sync")
    after = client.get("/api/rag/sync/status")

    assert before.status_code == 200
    assert before.json()["status"] == "idle"
    assert triggered.status_code == 200
    assert triggered.json()["status"] == "running"
    assert triggered.json()["stage"] == "download"
    assert after.status_code == 200
    assert after.json()["progress"] == 25
    assert after.json()["downloaded_files"] == ["course.md"]
    assert service.trigger_count == 1
