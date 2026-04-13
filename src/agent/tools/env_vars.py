from langchain.tools import tool

from agent.api.env_vars import list_env_var_keys


@tool
def list_global_env_vars() -> dict:
    """List global environment variable names available in the env vault.

    Returns keys only. Secret values are never exposed to the agent.
    """
    keys = list_env_var_keys()
    return {
        "success": True,
        "count": len(keys),
        "keys": keys,
    }
