"""Recommended topic endpoint scaffold."""

from __future__ import annotations

from fastapi import APIRouter

from api.errors import raise_not_implemented

router = APIRouter(tags=["icebreakers"])


@router.get("/chat/icebreakers")
async def get_icebreakers() -> dict:
    raise_not_implemented()
