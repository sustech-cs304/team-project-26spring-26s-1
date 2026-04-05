from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

import fastapi
from agent.db.database import Base, create_session_factory, create_sqlite_engine
from agent.api.conversation import router as conversation_router
from agent.api.conversation_runner import ConversationRunner
from agent.config import load_config, save_config
from agent.core.graph import create_graph

import aiosqlite
from langgraph.store.sqlite import AsyncSqliteStore
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

engine = None
async_session = None
config = None
graph = None

@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
	global engine, async_session, config, graph

	engine = create_sqlite_engine()
	async_session = create_session_factory(engine)
	config = load_config()
 
	store_conn = await aiosqlite.connect("agent_store.db", isolation_level=None)
	store = AsyncSqliteStore(store_conn)
	checkpointer_conn = await aiosqlite.connect("agent_checkpoints.db", isolation_level=None)
	checkpointer = AsyncSqliteSaver(checkpointer_conn)
 
	graph = await create_graph(config, store=store, checkpointer=checkpointer)
 
	app.state.engine = engine
	app.state.async_session = async_session
	app.state.ConversationRunner = ConversationRunner(graph, async_session)
	app.state.config = config
	app.state.graph = graph

	async with engine.begin() as conn:
		await conn.run_sync(Base.metadata.create_all)

	try:
		yield
  
	finally:
		await engine.dispose()
		await store_conn.close()
		await checkpointer_conn.close()

app = fastapi.FastAPI(lifespan=lifespan)
app.add_middleware(
	CORSMiddleware,
    allow_credentials=True, 
	allow_origins=["*"],
	allow_methods=["*"],
	allow_headers=["*"],
)
app.include_router(conversation_router, prefix="/api")