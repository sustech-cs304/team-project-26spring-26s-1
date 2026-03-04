"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .conversations import router as conversations_router
from .chat import router as chat_router
from .database import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    await init_db()
    yield
    await close_db()


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    app = FastAPI(
        title="默认模块",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.include_router(conversations_router)
    app.include_router(chat_router)

    return app


app = create_app()
