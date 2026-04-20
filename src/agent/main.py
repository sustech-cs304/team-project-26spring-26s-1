import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

import fastapi
from agent.calendar import start_calendar_sync
from agent.config import get_config
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
	telegram_bot = None

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
	if get_config().telegram.token.strip():
		from agent.im.telegram.bot import TelegramBot

		telegram_bot = TelegramBot(async_session, graph, app.state.ConversationRunner)
		await telegram_bot.start()
	app.state.TelegramBot = telegram_bot
	app.state.graph = graph
	app.state.NotificationService = notification_service
	configure_notification_service(notification_service)
	app.state.rag_cloud_sync_service = RagCloudSyncService()
	app.state.skills_hub_client = skills_hub_client
	app.state.skills_auth_state = skills_auth_state
	app.state.skills_local_store = skills_local_store

	calendar_sync_task = await start_calendar_sync(async_session)

	task_runtime = get_task_runtime()
	await task_runtime.start_scheduler(interval_s=60.0)
	log.info("Task scheduler started")

	try:
		yield
  
	finally:
		configure_notification_service(None)
		if telegram_bot is not None:
			await telegram_bot.stop()
		calendar_sync_task.cancel()
		try:
			await calendar_sync_task
		except asyncio.CancelledError:
			pass
		await task_runtime.aclose()
		log.info("Task scheduler stopped")
		await dispose_default_async_engine()
		await store_conn.close()
		await checkpointer_conn.close()

app = fastapi.FastAPI(lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_: fastapi.Request, __: RequestValidationError):
	return JSONResponse(status_code=400, content={"message": "Invalid request parameters"})

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
