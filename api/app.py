"""FastAPI application entrypoint for the API scaffold."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.adapters.agent_adapter import AgentAdapter
from api.constants import APP_NAME, APP_VERSION
from api.db.initializer import initialize_database
from api.db.session import dispose_async_engine, init_async_engine
from api.routers import include_all_routers
from api.runtime.manager import ConversationRuntimeManager
from api.settings import APISettings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = APISettings.from_env()
    init_async_engine(settings.database_url)
    await initialize_database()

    adapter = AgentAdapter()
    app.state.runtime_manager = ConversationRuntimeManager(adapter=adapter)

    try:
        yield
    finally:
        await dispose_async_engine()


def create_app() -> FastAPI:
    app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)
    include_all_routers(app)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = APISettings.from_env()
    uvicorn.run("api.app:app", host=settings.host, port=settings.port, reload=settings.reload)


if __name__ == "__main__":
    main()
