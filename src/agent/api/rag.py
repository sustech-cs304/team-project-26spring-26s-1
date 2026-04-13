from __future__ import annotations
from fastapi import APIRouter,  Request
from agent.rag.cloud_sync import RagCloudSyncService
from src.agent.api.rag_models import RagCloudSyncStatusResponse

router = APIRouter()


@router.post("/rag/sync", response_model=RagCloudSyncStatusResponse)
async def trigger_rag_cloud_sync(request: Request) -> RagCloudSyncStatusResponse:
    service: RagCloudSyncService = request.app.state.rag_cloud_sync_service
    status = await service.trigger_sync()
    return RagCloudSyncStatusResponse.model_validate(status)


@router.get("/rag/sync/status", response_model=RagCloudSyncStatusResponse)
async def get_rag_cloud_sync_status(request: Request) -> RagCloudSyncStatusResponse:
    service: RagCloudSyncService = request.app.state.rag_cloud_sync_service
    return RagCloudSyncStatusResponse.model_validate(service.get_status())
