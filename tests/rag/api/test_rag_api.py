from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent.api.rag import router as rag_router


pytestmark = pytest.mark.api


class FakeRagCloudSyncService:
    def __init__(self):
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
        self.status = {
            **self.status,
            "status": "running",
            "stage": "manifest",
            "progress": 5,
            "message": "Fetching cloud manifest.",
        }
        return self.status

    def get_status(self):
        return self.status


class RaisingRagCloudSyncService(FakeRagCloudSyncService):
    async def trigger_sync(self):
        raise RuntimeError("sync failed")

    def get_status(self):
        raise RuntimeError("status failed")


class MalformedRagCloudSyncService(FakeRagCloudSyncService):
    async def trigger_sync(self):
        return {"status": "running"}

    def get_status(self):
        return {"status": "idle"}


def test_rag_sync_api_uses_app_scoped_service(app_factory):
    service = FakeRagCloudSyncService()
    app = app_factory()
    app.state.rag_cloud_sync_service = service
    app.include_router(rag_router, prefix="/api")
    client = TestClient(app)

    initial = client.get("/api/rag/sync/status")
    triggered = client.post("/api/rag/sync")
    status = client.get("/api/rag/sync/status")

    assert initial.status_code == 200
    assert initial.json()["status"] == "idle"
    assert triggered.status_code == 200
    assert triggered.json()["status"] == "running"
    assert status.json()["stage"] == "manifest"


def test_rag_sync_status_response_covers_boundary_values(app_factory):
    service = FakeRagCloudSyncService()
    service.status = {
        "status": "completed",
        "stage": "done",
        "progress": 100,
        "message": "<script>alert(1)</script>",
        "knowledge_base_id": "kb-1",
        "version": "2026-05-15",
        "downloaded_files": ["a.md", "b.md"],
        "embedded_added": 0,
        "embedded_overwritten": 999999,
        "embedded_failed": 1,
        "error": None,
    }
    app = app_factory()
    app.state.rag_cloud_sync_service = service
    app.include_router(rag_router, prefix="/api")
    client = TestClient(app)

    response = client.get("/api/rag/sync/status")

    assert response.status_code == 200
    assert response.json()["progress"] == 100
    assert response.json()["downloaded_files"] == ["a.md", "b.md"]


@pytest.mark.xfail(strict=True, reason="Known issue: RAG API returns a generic 500 when app-scoped service is missing.")
def test_rag_sync_status_should_report_service_missing_as_503(app_factory):
    app = app_factory()
    app.include_router(rag_router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/rag/sync/status")

    assert response.status_code == 503


@pytest.mark.xfail(strict=True, reason="Known issue: RAG API returns a generic 500 when app-scoped service is missing.")
def test_rag_sync_trigger_should_report_service_missing_as_503(app_factory):
    app = app_factory()
    app.include_router(rag_router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/api/rag/sync")

    assert response.status_code == 503


@pytest.mark.parametrize(("method", "url"), [("POST", "/api/rag/sync"), ("GET", "/api/rag/sync/status")])
def test_rag_sync_api_returns_500_when_service_raises(app_factory, method, url):
    app = app_factory()
    app.state.rag_cloud_sync_service = RaisingRagCloudSyncService()
    app.include_router(rag_router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.request(method, url)

    assert response.status_code == 500


@pytest.mark.parametrize(("method", "url"), [("POST", "/api/rag/sync"), ("GET", "/api/rag/sync/status")])
def test_rag_sync_api_returns_500_for_malformed_service_status(app_factory, method, url):
    app = app_factory()
    app.state.rag_cloud_sync_service = MalformedRagCloudSyncService()
    app.include_router(rag_router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.request(method, url)

    assert response.status_code == 500
