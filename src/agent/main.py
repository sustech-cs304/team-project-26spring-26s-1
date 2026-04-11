import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

import fastapi
from agent.db.database import Base, create_session_factory, create_sqlite_engine
from agent.api.conversation import router as conversation_router
from agent.api.file import router as file_router
from agent.api.onebot import OneBotHub, router as onebot_router
from agent.api.rag import router as rag_router
from agent.api.conversation_runner import ConversationRunner
from agent.config import config
from agent.core.graph import create_graph
from agent.api.onebot import OneBotHub
from agent.api.task import router as task_router
from agent.api.env_vars import router as env_vars_router
from agent.api.school_settings import router as school_settings_router
from agent.api.routine_events import ensure_routine_calendar_schema, router as routine_events_router
from agent.cron_watcher import CronWatcher
from agent.task_executor import ensure_task_run_sqlite_schema

import aiosqlite
from langgraph.store.sqlite import AsyncSqliteStore
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sqlalchemy import event

log = logging.getLogger("main")

engine = None
async_session = None
graph = None

@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
	global engine, async_session, config, graph

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
 
	graph = await create_graph(config, store=store, checkpointer=checkpointer)
 
	app.state.engine = engine
	app.state.async_session = async_session
	app.state.ConversationRunner = ConversationRunner(graph, async_session, config)
	app.state.OneBotHub = OneBotHub(async_session, graph, app.state.ConversationRunner, config.onebot)
	app.state.config = config
	app.state.graph = graph

	async with engine.begin() as conn:
		await conn.run_sync(Base.metadata.create_all)

	async with async_session() as session:
		await ensure_routine_calendar_schema(session)
		await session.commit()

	await asyncio.to_thread(ensure_task_run_sqlite_schema)

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
app.include_router(school_settings_router, prefix="/api")
app.include_router(routine_events_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
