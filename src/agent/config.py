from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

import yaml
from jinja2 import Environment, PackageLoader, select_autoescape
from pydantic import BaseModel, Field

jinja_env = Environment(
    loader=PackageLoader("agent"),
    autoescape=select_autoescape()
)

class ApiEndpointConfig(BaseModel):
    type: Literal["OpenAI", "Qwen", "Anthropic"]
    base_url: str
    api_key: str
    model: str

class EmbedEndpointConfig(BaseModel):
    type: Literal["OpenAI"]
    base_url: str
    api_key: str
    model: str
    dims: int

class ASREndpointConfig(BaseModel):
    type: Literal["Qwen"]
    base_url: str
    api_key: str

class ApiConfig(BaseModel):
    agent: ApiEndpointConfig
    utility: ApiEndpointConfig
    embed: EmbedEndpointConfig
    rerank: ApiEndpointConfig
    asr: ASREndpointConfig

class MineruConfig(BaseModel):
    base_url: str
    api_key: str

class FileConfig(BaseModel):
    upload_path: str
    mineru: MineruConfig

class WebFetchConfig(BaseModel):
    base_url: str
    api_key: str
    path: str = "/api/fetch"
    timeout_ms: int = 30000

class WebSearchConfig(BaseModel):
    base_url: str
    api_key: str
    path: str = "/api/search"
    timeout_ms: int = 30000

class OneBotConfig(BaseModel):
    access_token: str = ""
    superuser_id: str = ""
    command_name: str = "agent"

class NotificationConfig(BaseModel):
    enabled: bool = True
    app_name: str = "Agent"
    app_icon: str | None = "assets/opencrab.png"
    notification_limit: int | None = 8
    default_timeout_s: int = 10
    deeplink_scheme: str = "opencrab"

class AppConfig(BaseModel):
    api: ApiConfig
    file: FileConfig
    webfetch: WebFetchConfig
    websearch: WebSearchConfig
    onebot: OneBotConfig = Field(default_factory=OneBotConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)


DEFAULT_CONFIG_PATH = "config.yaml"


def _merge_config_dict(base: dict[str, Any], delta: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in delta.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config_dict(merged[key], value)
            continue
        merged[key] = value
    return merged


def load_config(file_path: str = DEFAULT_CONFIG_PATH) -> AppConfig:
    """Loads config.yaml into a verified Pydantic object with env var lookups."""
    with open(file_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}

    return AppConfig.model_validate(config_data)


_config = load_config()


def get_config() -> AppConfig:
    return _config


def patch_config(delta: Mapping[str, Any]) -> AppConfig:
    """Apply a validated partial update to the live config."""
    global _config
    merged = _merge_config_dict(_config.model_dump(), delta)
    _config = AppConfig.model_validate(merged)
    return _config


def reload_config(file_path: str = DEFAULT_CONFIG_PATH) -> AppConfig:
    """Reload the live config from disk."""
    global _config
    _config = load_config(file_path)
    return _config


def save_config(config_to_save: AppConfig | None = None, file_path: str = DEFAULT_CONFIG_PATH):
    """Saves the Pydantic config object back to a YAML file."""
    current_config = get_config() if config_to_save is None else config_to_save
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(current_config.model_dump(), f, sort_keys=False)