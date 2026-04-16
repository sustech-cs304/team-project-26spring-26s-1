import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

import fastapi
from agent.config import get_config
from agent.db.database import Base, create_session_factory, create_sqlite_engine
from agent.api.conversation import router as conversation_router
from agent.api.file import router as file_router
from agent.api.notifications import router as notifications_router
from agent.api.onebot import OneBotHub, router as onebot_router
from agent.api.rag import router as rag_router
from agent.api.skills import router as skills_router
from agent.api.conversation_runner import ConversationRunner
from agent.core.graph import create_graph
from agent.notifications import configure_notification_service
from agent.api.task import router as task_router
from agent.api.env_vars import router as env_vars_router
from agent.api.config import router as config_router
from agent.api.school_settings import router as school_settings_router
from agent.api.routine_events import (
	BB_SOURCE_TITLE,
	TIS_SOURCE_TITLE,
	ensure_routine_calendar_schema,
	router as routine_events_router,
	sync_managed_source,
)
from agent.cron_watcher import CronWatcher
from agent.rag.cloud_sync import RagCloudSyncService
from agent.task_executor import ensure_task_run_sqlite_schema
from agent.services import NotificationService, SkillsAuthState, SkillsHubClient, SkillsLocalStore

import aiosqlite
from langgraph.store.sqlite import AsyncSqliteStore
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sqlalchemy import event
import os

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

log = logging.getLogger("main")

engine = None
async_session = None
graph = None
_CALENDAR_SYNC_INTERVAL_SECONDS = 15 * 60
_CALENDAR_SYNC_SOURCES = (BB_SOURCE_TITLE, TIS_SOURCE_TITLE)


async def _sync_calendar_source_once(source_id: str) -> None:
	global async_session

	if async_session is None:
		return

	async with async_session() as session:
		try:
			result = await sync_managed_source(source_id, session)
			await session.commit()
			log.info(
				"Calendar source sync completed",
				extra={"source_id": source_id, "event_count": len(result.get("ids", []))},
			)
		except asyncio.CancelledError:
			await session.rollback()
			raise
		except Exception:
			await session.rollback()
			log.exception("Calendar source sync failed", extra={"source_id": source_id})


async def _sync_calendar_sources_once() -> None:
	await asyncio.gather(*(_sync_calendar_source_once(source_id) for source_id in _CALENDAR_SYNC_SOURCES))


async def _run_periodic_calendar_sync() -> None:
	try:
		while True:
			await asyncio.sleep(_CALENDAR_SYNC_INTERVAL_SECONDS)
			await _sync_calendar_sources_once()
	except asyncio.CancelledError:
		log.info("Calendar sync background task stopped")
		raise

@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
	global engine, async_session, graph

	engine = create_sqlite_engine()
	@event.listens_for(engine.sync_engine, "connect")
	def set_sqlite_pragma(dbapi_connection, _):
		cursor = dbapi_connection.cursor()
		cursor.execute("PRAGMA foreign_keys=ON")
		cursor.close()
	async_session = create_session_factory(engine)
 
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
	app.state.graph = graph
	app.state.NotificationService = notification_service
	configure_notification_service(notification_service)
	app.state.rag_cloud_sync_service = RagCloudSyncService()
	app.state.skills_hub_client = skills_hub_client
	app.state.skills_auth_state = skills_auth_state
	app.state.skills_local_store = skills_local_store

	async with engine.begin() as conn:
		await conn.run_sync(Base.metadata.create_all)

	async with async_session() as session:
		await ensure_routine_calendar_schema(session)
		await session.commit()

	await asyncio.to_thread(ensure_task_run_sqlite_schema)

	await _sync_calendar_sources_once()
	calendar_sync_task = asyncio.create_task(
		_run_periodic_calendar_sync(),
		name="calendar-source-sync",
	)
	log.info("Calendar source sync task started")

	watcher = CronWatcher(max_workers=4, timeout=300)
	watcher_thread = threading.Thread(
		target=watcher.run,
		kwargs={"interval": 60},
		daemon=True,
		name="cron-watcher",
	)
	watcher_thread.start()
	log.info("CronWatcher background thread started")

	try:
		yield
  
	finally:
		configure_notification_service(None)
		calendar_sync_task.cancel()
		try:
			await calendar_sync_task
		except asyncio.CancelledError:
			pass
		watcher.stop()
		watcher_thread.join(timeout=5)
		if watcher_thread.is_alive():
			log.warning(
				"CronWatcher thread did not exit within 5s (daemon may still be running)",
			)
		else:
			log.info("CronWatcher stopped")
		await engine.dispose()
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
