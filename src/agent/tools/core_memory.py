from langgraph.store.base import BaseStore
from langchain.tools import tool, ToolRuntime

NAMESPACE = "core_memory"

ENTRY_LIMIT = 1000

async def core_memory_get(store: BaseStore) -> list[tuple[str, str]]:
    mem = await store.asearch((NAMESPACE,), limit=ENTRY_LIMIT)
    return [(entry.key, entry.value['data']) for entry in mem]

@tool
async def core_memory_insert(runtime: ToolRuntime, key: str, value: str):
    """Inserts a key-value pair into core memory."""
    store = runtime.store
    if store:
        await store.aput((NAMESPACE,), key=key, value={"data": value})
        print(f"Inserted key '{key}' into core memory.")
        return f"Inserted key '{key}' into core memory."