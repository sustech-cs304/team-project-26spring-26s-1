from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["mcp"])


@router.get(
    "/mcp",
    summary="获取mcp状态",
)
async def get_mcp_status(request: Request) -> list[dict[str, str]]:
    mcp_manager = request.app.state.MCPLifespanManager
    return mcp_manager.get_statuses()
