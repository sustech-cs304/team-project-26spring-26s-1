import threading
from typing import Literal

import yaml
from pydantic import BaseModel
from jinja2 import Environment, PackageLoader, select_autoescape

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

class AppConfig(BaseModel):
    api: ApiConfig
    file: FileConfig
    webfetch: WebFetchConfig
    websearch: WebSearchConfig
    onebot: OneBotConfig = OneBotConfig()


class _ConfigHolder:
    __slots__ = ("_lock", "_config")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._config: AppConfig | None = None

    def set(self, config: AppConfig) -> None:
        with self._lock:
            self._config = config

    def get(self) -> AppConfig:
        with self._lock:
            if self._config is None:
                self._config = load_config()
            return self._config


_holder = _ConfigHolder()


def get_config() -> AppConfig:
    """Current in-memory config (replace via :func:`set_config` or :func:`reload_config`)."""
    return _holder.get()


def set_config(config: AppConfig) -> None:
    """Install config (e.g. after startup or admin reload)."""
    _holder.set(config)


def load_config(file_path: str = "config.yaml") -> AppConfig:
    """Load ``config.yaml`` into a verified model."""
    with open(file_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}
    return AppConfig(**config_data)


def save_config(config: AppConfig, file_path: str = "config.yaml") -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config.model_dump(), f)


def reload_config(file_path: str = "config.yaml") -> AppConfig:
    """Reload from disk and apply to the global holder."""
    cfg = load_config(file_path)
    set_config(cfg)
    return cfg
