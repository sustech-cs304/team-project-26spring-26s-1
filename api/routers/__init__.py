"""Router registration helper."""

from __future__ import annotations

from fastapi import FastAPI

from .cancel import router as cancel_router
from .completion import router as completion_router
from .conversation import router as conversation_router
from .conversations import router as conversations_router
from .icebreakers import router as icebreakers_router


def include_all_routers(app: FastAPI) -> None:
    app.include_router(conversation_router)
    app.include_router(completion_router)
    app.include_router(conversations_router)
    app.include_router(cancel_router)
    app.include_router(icebreakers_router)
