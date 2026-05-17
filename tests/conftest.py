from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Callable

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


MINIMAL_CONFIG = """
api:
  agent:
    type: OpenAI
    base_url: http://localhost
    api_key: test
    model: test
  utility:
    type: OpenAI
    base_url: http://localhost
    api_key: test
    model: test
  embed:
    type: OpenAI
    base_url: http://localhost
    api_key: test
    model: test
    dims: 1536
  rerank:
    type: OpenAI
    base_url: http://localhost
    api_key: test
    model: test
  asr:
    type: Qwen
    base_url: ws://localhost
    api_key: test
file:
  upload_path: ./uploads
  rag_path: ./rag
  mineru:
    base_url: http://localhost
    api_key: test
webfetch:
  base_url: http://localhost
  api_key: test
websearch:
  base_url: http://localhost
  api_key: test
notification:
  enabled: false
  app_name: OpenCrab Test
  app_icon: null
  deeplink_scheme: opencrab
"""


if not Path("config.yaml").exists():
    Path("config.yaml").write_text(MINIMAL_CONFIG, encoding="utf-8")

os.environ.setdefault("AGENT_ENV_VAULT_MASTER_KEY", "test-master-key")


@pytest.fixture
def run_async() -> Callable:
    def _run(coro):
        return asyncio.run(coro)

    return _run


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite+aiosqlite:///{db_path.as_posix()}"


@pytest.fixture
def sqlite_session_factory(tmp_path):
    from agent.db.database import Base, create_session_factory, create_sqlite_engine

    engine = create_sqlite_engine(_sqlite_url(tmp_path / "test.db"))
    session_factory = create_session_factory(engine)

    async def _init_schema():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init_schema())
    try:
        yield session_factory
    finally:
        asyncio.run(engine.dispose())


@pytest.fixture
def temp_default_db(monkeypatch, tmp_path):
    import agent.db.database as database

    engine = database.create_sqlite_engine(_sqlite_url(tmp_path / "default.db"))
    session_factory = database.create_session_factory(engine)

    async def _init_schema():
        async with engine.begin() as conn:
            await conn.run_sync(database.Base.metadata.create_all)

    asyncio.run(_init_schema())
    monkeypatch.setattr(database, "_default_engine", engine)
    monkeypatch.setattr(database, "_default_session_factory", session_factory)
    monkeypatch.setattr(database, "_schema_ready", True)
    try:
        yield session_factory
    finally:
        asyncio.run(engine.dispose())
        monkeypatch.setattr(database, "_default_engine", None)
        monkeypatch.setattr(database, "_default_session_factory", None)
        monkeypatch.setattr(database, "_schema_ready", False)


@pytest.fixture
def app_factory():
    def _factory() -> FastAPI:
        app = FastAPI()

        @app.exception_handler(RequestValidationError)
        async def request_validation_exception_handler(_, __):
            return JSONResponse(status_code=400, content={"message": "Invalid request parameters"})

        return app

    return _factory
