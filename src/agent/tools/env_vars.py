from langchain.tools import tool

from agent.api.env_vars import list_env_var_keys


@tool
async def list_global_env_vars() -> dict:
    """List global environment variable names available in the shared credential store.

    Returns keys only. Secret values are never exposed to the agent.
    """
    keys = await list_env_var_keys()
    return {
        "success": True,
        "count": len(keys),
        "keys": keys,
    }
