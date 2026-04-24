from collections.abc import Mapping
from typing import Any

from langchain_core.runnables import RunnableConfig


def runnable_config_bool(config: RunnableConfig | Mapping[str, Any] | None, key: str) -> bool:
    if not isinstance(config, Mapping):
        return False

    if config.get(key) is True:
        return True

    configurable = config.get("configurable")
    if isinstance(configurable, Mapping) and configurable.get(key) is True:
        return True

    metadata = config.get("metadata")
    return isinstance(metadata, Mapping) and metadata.get(key) is True
