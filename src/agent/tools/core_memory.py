import logging

from langgraph.store.base import BaseStore
from langchain.tools import tool, ToolRuntime

log = logging.getLogger(__name__)
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
        log.info("Inserted key '%s' into core memory.", key)
        return f"Inserted key '{key}' into core memory."
    return "Error: Store is not available from runtime."


@tool
async def core_memory_modify(
    runtime: ToolRuntime,
    key: str,
    old_substring: str,
    new_substring: str,
):
    """Modify an existing core memory entry by replacing the first matching substring.
    To erase an entry's contents, replace the full current value with an empty string."""
    
    store = runtime.store
    if not store:
        return "Error: Store is not available from runtime."

    if not old_substring:
        return "Error: old_substring must not be empty."

    item = await store.aget((NAMESPACE,), key)
    if item is None:
        return f"Error: Core memory entry '{key}' does not exist."

    current_value = item.value.get("data")
    if not isinstance(current_value, str):
        return f"Error: Core memory entry '{key}' is invalid."

    if old_substring not in current_value:
        return f"Error: Substring not found in core memory entry '{key}'."

    updated_value = current_value.replace(old_substring, new_substring, 1)
    if updated_value == "":
        await store.adelete((NAMESPACE,), key)
        log.info("Erased key '%s' in core memory.", key)
        return f"Erased key '{key}' in core memory."

    await store.aput((NAMESPACE,), key=key, value={"data": updated_value})
    log.info("Modified key '%s' in core memory.", key)
    return f"Modified key '{key}' in core memory."
