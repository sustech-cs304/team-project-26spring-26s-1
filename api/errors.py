"""Error helpers used by routers/services."""

from __future__ import annotations

from fastapi import HTTPException, status

from .constants import NOT_IMPLEMENTED_DETAIL


def raise_not_implemented() -> None:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=NOT_IMPLEMENTED_DETAIL)
