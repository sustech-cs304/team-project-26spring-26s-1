import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

import fastapi
from agent.calendar import CalendarSyncRuntime
from agent.config import get_config
from agent.config_runtime import ConfigManager
from agent.db.database import (
	dispose_default_async_engine,
	ensure_default_schema,
	get_default_async_engine,
	get_default_session_factory,
)
from agent.api.conversation import router as conversation_router
from agent.api.file import router as file_router
from agent.api.notifications import router as notifications_router
from agent.im.onebot import OneBotHub, router as onebot_router
from agent.api.rag import router as rag_router
from agent.api.skills import router as skills_router
from agent.api.conversation_runner import ConversationRunner
from agent.core.graph import create_graph
from agent.notifications import configure_notification_service
from agent.api.task import router as task_router
from agent.api.env_vars import router as env_vars_router
from agent.api.config import router as config_router
from agent.api.school_settings import router as school_settings_router
from agent.api.routine_events import router as routine_events_router
from agent.rag.cloud_sync import RagCloudSyncService
from agent.services.task_runtime import get_task_runtime
from agent.services import NotificationService, SkillsAuthState, SkillsHubClient, SkillsLocalStore
from agent.im.telegram.runtime import TelegramRuntime

import aiosqlite
from langgraph.store.sqlite import AsyncSqliteStore
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import os

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

log = logging.getLogger("main")

engine = None
async_session = None
graph = None

@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
	global engine, async_session, graph

	engine = get_default_async_engine()
	async_session = get_default_session_factory()
 
	store_conn = await aiosqlite.connect("agent_store.db", isolation_level=None)
	store = AsyncSqliteStore(store_conn)
	checkpointer_conn = await aiosqlite.connect("agent_checkpoints.db", isolation_level=None)
	checkpointer = AsyncSqliteSaver(checkpointer_conn)
 
	graph = await create_graph(store=store, checkpointer=checkpointer)
	notification_service = NotificationService(asyncio.get_running_loop())
	skills_hub_client = SkillsHubClient()
	skills_auth_state = SkillsAuthState()
	skills_local_store = SkillsLocalStore(
		async_session,
		get_config().skills_cloud.local_store_path,
	)
 
	app.state.engine = engine
	app.state.async_session = async_session
	app.state.ConversationRunner = ConversationRunner(graph, async_session)
	app.state.OneBotHub = OneBotHub(async_session, graph, app.state.ConversationRunner)
	await ensure_default_schema()
	config_manager = ConfigManager()
	telegram_runtime = TelegramRuntime(async_session, graph, app.state.ConversationRunner)
	await telegram_runtime.start(get_config())
	calendar_sync_runtime = CalendarSyncRuntime(async_session)
	await calendar_sync_runtime.start()
	config_manager.subscribe(telegram_runtime)
	config_manager.subscribe(calendar_sync_runtime)
	app.state.ConfigManager = config_manager
	app.state.TelegramRuntime = telegram_runtime
	app.state.CalendarSyncRuntime = calendar_sync_runtime
	app.state.graph = graph
	app.state.NotificationService = notification_service
	configure_notification_service(notification_service)
	app.state.rag_cloud_sync_service = RagCloudSyncService()
	app.state.skills_hub_client = skills_hub_client
	app.state.skills_auth_state = skills_auth_state
	app.state.skills_local_store = skills_local_store

	task_runtime = get_task_runtime()
	await task_runtime.start_scheduler(interval_s=60.0)
	log.info("Task scheduler started")

	try:
		yield
  
	finally:
		configure_notification_service(None)
		await telegram_runtime.stop()
		await calendar_sync_runtime.stop()
		await task_runtime.aclose()
		log.info("Task scheduler stopped")
		await dispose_default_async_engine()
		await store_conn.close()
		await checkpointer_conn.close()

app = fastapi.FastAPI(lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_: fastapi.Request, __: RequestValidationError):
	return JSONResponse(status_code=400, content={"message": "Invalid request parameters"})


@app.post("/internal/shutdown")
async def shutdown_backend(
	request: fastapi.Request,
	background_tasks: fastapi.BackgroundTasks,
):
	server = getattr(request.app.state, "uvicorn_server", None)
	if server is None:
		raise fastapi.HTTPException(status_code=503, detail="Shutdown unavailable")

	background_tasks.add_task(setattr, server, "should_exit", True)
	return {"status": "shutting_down"}

app.add_middleware(
	CORSMiddleware,
    allow_credentials=True, 
	allow_origins=["*"],
	allow_methods=["*"],
	allow_headers=["*"],
)
app.include_router(conversation_router, prefix="/api")
app.include_router(file_router, prefix="/api")
app.include_router(onebot_router, prefix="/api")
app.include_router(task_router, prefix="/api")
app.include_router(env_vars_router, prefix="/api")
app.include_router(config_router, prefix="/api")
app.include_router(school_settings_router, prefix="/api")
app.include_router(routine_events_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(skills_router, prefix="/api")


def main() -> int:
	import argparse
	import uvicorn

	parser = argparse.ArgumentParser()
	parser.add_argument("--host", default="127.0.0.1")
	parser.add_argument("--port", default=8000, type=int)
	args = parser.parse_args()
	config = uvicorn.Config(app, host=args.host, port=args.port)
	server = uvicorn.Server(config)
	app.state.uvicorn_server = server
	server.run()
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
