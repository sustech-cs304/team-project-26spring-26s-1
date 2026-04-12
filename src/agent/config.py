import logging
import threading
from pathlib import Path
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


class SchoolServiceCredentials(BaseModel):
    """``student_id`` plus ``password_enc`` (Fernet) or optional plaintext ``password`` (local only)."""

    student_id: str = ""
    password_enc: str = ""
    password: str = ""


class SchoolFileConfig(BaseModel):
    """Fernet key (url-safe base64) for ``password_enc`` fields under ``bb`` / ``tis``."""

    fernet_key: str = ""
    bb: SchoolServiceCredentials = SchoolServiceCredentials()
    tis: SchoolServiceCredentials = SchoolServiceCredentials()


class AppConfig(BaseModel):
    api: ApiConfig
    file: FileConfig
    webfetch: WebFetchConfig
    websearch: WebSearchConfig
    onebot: OneBotConfig = OneBotConfig()
    school: SchoolFileConfig = SchoolFileConfig()
    # IANA id (e.g. Asia/Shanghai). Cron fields are evaluated in this zone; schedules are still stored as UTC instants.
    cron_timezone: str = "UTC"


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

_log = logging.getLogger(__name__)


def project_root() -> Path:
    """Repository root (directory that contains ``config.yaml`` / ``pyproject.toml``)."""
    return Path(__file__).resolve().parent.parent.parent


def resolve_config_path(file_path: str | Path | None = None) -> Path:
    """Resolve ``config.yaml`` against :func:`project_root` when the path is relative."""
    p = Path(file_path or "config.yaml")
    if p.is_absolute():
        return p
    return project_root() / p


def get_config() -> AppConfig:
    """Current in-memory config (replace via :func:`set_config` or :func:`reload_config`)."""
    return _holder.get()


def set_config(config: AppConfig) -> None:
    """Install config (e.g. after startup or admin reload)."""
    _holder.set(config)


def load_config(file_path: str | Path | None = None) -> AppConfig:
    """Load ``config.yaml`` into a verified model.

    Paths are resolved from the repository root (not the process current working directory),
    unless ``file_path`` is absolute.
    """
    path = resolve_config_path(file_path)
    _log.info("Loading config from %s", path)
    with open(path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}
    return AppConfig(**config_data)


def save_config(config: AppConfig, file_path: str | Path | None = None) -> None:
    path = resolve_config_path(file_path)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config.model_dump(), f)


def reload_config(file_path: str | Path | None = None) -> AppConfig:
    """Reload from disk and apply to the global holder."""
    cfg = load_config(file_path)
    set_config(cfg)
    return cfg
