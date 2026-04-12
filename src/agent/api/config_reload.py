"""Reload ``config.yaml`` without process restart."""
from fastapi import APIRouter

from agent.config import reload_config

router = APIRouter(tags=["config"])


@router.post("/config/reload")
async def reload_config_endpoint() -> dict:
    """Reload ``config.yaml`` into memory. New requests use the updated config."""
    reload_config()
    return {"ok": True, "message": "Config reloaded"}
