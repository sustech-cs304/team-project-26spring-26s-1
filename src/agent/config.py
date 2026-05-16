from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path
from types import UnionType
from typing import Annotated, Any, Literal, Union, get_args, get_origin

import yaml
from jinja2 import Environment, PackageLoader, select_autoescape
from pydantic import BaseModel, Field

jinja_env = Environment(
    loader=PackageLoader("agent"),
    autoescape=select_autoescape()
)

SENSITIVE_CONFIG_META_KEY = "x-sensitive"
REDACTED_CONFIG_VALUE = "********"
SensitiveStr = Annotated[str, Field(json_schema_extra={SENSITIVE_CONFIG_META_KEY: True})]

class LLMEndpointConfig(BaseModel):
    type: Literal["OpenAI", "Qwen", "Anthropic"] = "OpenAI"
    base_url: str = ""
    api_key: SensitiveStr = ""
    model: str = ""
    max_token_count: int = Field(default=128000, ge=1)

class RerankerEndpointConfig(BaseModel):
    type: Literal["OpenAI"] = "OpenAI"
    base_url: str = ""
    api_key: SensitiveStr = ""
    model: str = ""

class EmbedEndpointConfig(BaseModel):
    type: Literal["OpenAI"] = "OpenAI"
    base_url: str = ""
    api_key: SensitiveStr = ""
    model: str = ""
    dims: int = 1536

class ASREndpointConfig(BaseModel):
    type: Literal["Qwen"] = "Qwen"
    base_url: str = ""
    api_key: SensitiveStr = ""

class ApiConfig(BaseModel):
    agent: LLMEndpointConfig = Field(default_factory=LLMEndpointConfig)
    utility: LLMEndpointConfig = Field(default_factory=LLMEndpointConfig)
    embed: EmbedEndpointConfig = Field(default_factory=EmbedEndpointConfig)
    rerank: RerankerEndpointConfig = Field(default_factory=RerankerEndpointConfig)
    asr: ASREndpointConfig = Field(default_factory=ASREndpointConfig)

class MineruConfig(BaseModel):
    base_url: str = ""
    api_key: SensitiveStr = ""

class FileConfig(BaseModel):
    upload_path: str = "./uploads"
    rag_path: str = "./rag"
    mineru: MineruConfig = Field(default_factory=MineruConfig)

class WebFetchConfig(BaseModel):
    base_url: str = ""
    api_key: SensitiveStr = ""
    path: str = "/api/fetch"
    timeout_ms: int = 30000

class WebSearchConfig(BaseModel):
    base_url: str = ""
    api_key: SensitiveStr = ""
    path: str = "/api/search"
    timeout_ms: int = 30000

class OneBotConfig(BaseModel):
    access_token: SensitiveStr = ""
    superuser_ids: list[str] = Field(default_factory=list)
    command_trigger: str = "/agent"
    message_trigger: str = "/"


class TelegramConfig(BaseModel):
    token: SensitiveStr = ""
    superuser_ids: list[str] = Field(default_factory=list)
    command_trigger: str = "/agent"
    message_trigger: str = "/"

class NotificationConfig(BaseModel):
    enabled: bool = True
    app_name: str = "Agent"
    app_icon: str | None = "assets/opencrab.png"
    notification_limit: int | None = 8
    default_timeout_s: int = 10
    deeplink_scheme: str = "opencrab"


class RagCloudConfig(BaseModel):
    base_url: str = ""
    manifest_path: str = "manifest.json"
    timeout_ms: int = 30000
    api_key: SensitiveStr = ""

class CodeInterpreterConfig(BaseModel):
    default_timeout_s: float = Field(default=10.0, gt=0)
    auto_approve_max_risk_level: Literal["Low", "Medium", "High"] = "Low"


class SkillsCloudConfig(BaseModel):
    base_url: str = ""
    timeout_ms: int = 30000
    delete_submission_path: str = ""
    local_store_path: str = "./workspace/skills"


class MCPConfig(BaseModel):
    url: str
    token: str | None = None
    enabled_by_default: bool = False

class AppConfig(BaseModel):
    api: ApiConfig = Field(default_factory=ApiConfig)
    file: FileConfig = Field(default_factory=FileConfig)
    webfetch: WebFetchConfig = Field(default_factory=WebFetchConfig)
    websearch: WebSearchConfig = Field(default_factory=WebSearchConfig)
    onebot: OneBotConfig = Field(default_factory=OneBotConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    rag_cloud: RagCloudConfig = RagCloudConfig()
    skills_cloud: SkillsCloudConfig = Field(default_factory=SkillsCloudConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    code_interpreter: CodeInterpreterConfig = Field(default_factory=CodeInterpreterConfig)
    mcp: dict[str, MCPConfig] = Field(default_factory=dict)


DEFAULT_CONFIG_PATH = "config.yaml"


_DICT_ORIGINS = {dict, Mapping, MutableMapping}
_UNION_ORIGINS = {Union, UnionType}


class ConfigMissingError(RuntimeError):
    def __init__(self, path: str, fields: Sequence[str] = ()):
        self.path = path
        self.fields = tuple(fields)
        if self.fields:
            field_names = ", ".join(self.fields)
            message = f"{path} is not configured. Missing fields: {field_names}."
        else:
            message = f"{path} is not configured."
        super().__init__(message)


def _is_missing_config_value(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _normalize_config_path(path: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(path, str):
        return tuple(part for part in path.split(".") if part)
    return tuple(str(part) for part in path)


def _config_path_label(path: str | Sequence[str]) -> str:
    return ".".join(_normalize_config_path(path))


def get_config_path(config_obj: Any, path: str | Sequence[str]) -> Any:
    parts = _normalize_config_path(path)
    label = ".".join(parts)
    current = config_obj

    for index, part in enumerate(parts):
        current_label = ".".join(parts[: index + 1])
        if current is None:
            raise ConfigMissingError(current_label)
        if isinstance(current, Mapping):
            if part not in current:
                raise ConfigMissingError(current_label)
            current = current[part]
            continue
        if not hasattr(current, part):
            raise ConfigMissingError(current_label)
        current = getattr(current, part)

    if current is None:
        raise ConfigMissingError(label)
    return current


def require_config_fields(config_obj: Any, path: str, fields: Sequence[str]) -> Any:
    if config_obj is None:
        raise ConfigMissingError(path)

    if isinstance(config_obj, Mapping):
        missing_fields = [
            field
            for field in fields
            if field not in config_obj or _is_missing_config_value(config_obj.get(field))
        ]
    else:
        missing_fields = [
            field
            for field in fields
            if not hasattr(config_obj, field) or _is_missing_config_value(getattr(config_obj, field))
        ]
    if missing_fields:
        raise ConfigMissingError(path, missing_fields)
    return config_obj


def require_config_path(config_obj: Any, path: str | Sequence[str], fields: Sequence[str]) -> Any:
    label = _config_path_label(path)
    return require_config_fields(get_config_path(config_obj, path), label, fields)


def require_llm_endpoint_config(endpoint: LLMEndpointConfig | None, path: str) -> LLMEndpointConfig:
    return require_config_fields(endpoint, path, ("base_url", "api_key", "model"))


def require_embedding_config(endpoint: EmbedEndpointConfig | None, path: str = "api.embed") -> EmbedEndpointConfig:
    return require_config_fields(endpoint, path, ("base_url", "api_key", "model"))


def require_reranker_config(endpoint: RerankerEndpointConfig | None, path: str = "api.rerank") -> RerankerEndpointConfig:
    return require_config_fields(endpoint, path, ("base_url", "api_key", "model"))


def require_asr_config(endpoint: ASREndpointConfig | None, path: str = "api.asr") -> ASREndpointConfig:
    return require_config_fields(endpoint, path, ("base_url", "api_key"))


def require_mineru_config(config: MineruConfig | None, path: str = "file.mineru") -> MineruConfig:
    return require_config_fields(config, path, ("base_url", "api_key"))


def require_webfetch_config(config: WebFetchConfig | None, path: str = "webfetch") -> WebFetchConfig:
    return require_config_fields(config, path, ("base_url", "api_key"))


def require_websearch_config(config: WebSearchConfig | None, path: str = "websearch") -> WebSearchConfig:
    return require_config_fields(config, path, ("base_url", "api_key"))


def require_rag_cloud_config(config: RagCloudConfig | None, path: str = "rag_cloud") -> RagCloudConfig:
    return require_config_fields(config, path, ("base_url",))


def require_skills_cloud_config(config: SkillsCloudConfig | None, path: str = "skills_cloud") -> SkillsCloudConfig:
    return require_config_fields(config, path, ("base_url",))


def require_mcp_config(config: MCPConfig | None, path: str) -> MCPConfig:
    return require_config_fields(config, path, ("url",))


def _is_dict_annotation(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin in _UNION_ORIGINS:
        return any(
            _is_dict_annotation(arg)
            for arg in get_args(annotation)
            if arg is not type(None)
        )
    return annotation in _DICT_ORIGINS or origin in _DICT_ORIGINS


def _model_type_from_annotation(annotation: Any) -> type[BaseModel] | None:
    origin = get_origin(annotation)
    if origin in _UNION_ORIGINS:
        for arg in get_args(annotation):
            model_type = _model_type_from_annotation(arg)
            if model_type is not None:
                return model_type
        return None
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def _dict_value_model_type(annotation: Any) -> type[BaseModel] | None:
    origin = get_origin(annotation)
    if origin in _UNION_ORIGINS:
        for arg in get_args(annotation):
            model_type = _dict_value_model_type(arg)
            if model_type is not None:
                return model_type
        return None
    if origin not in _DICT_ORIGINS:
        return None
    args = get_args(annotation)
    if len(args) != 2:
        return None
    return _model_type_from_annotation(args[1])


def _field_annotation(model_type: type[BaseModel] | None, key: str) -> Any:
    if model_type is None:
        return None
    field = model_type.model_fields.get(key)
    if field is None:
        return None
    return field.annotation


def _merge_dict_field(
    base: dict[str, Any],
    delta: Mapping[str, Any],
    value_model_type: type[BaseModel] | None,
) -> dict[str, Any]:
    merged = dict(base)
    for key, value in delta.items():
        if value is None:
            merged.pop(key, None)
            continue
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config_dict(merged[key], value, value_model_type)
            continue
        merged[key] = value
    return merged


def _merge_config_dict(
    base: dict[str, Any],
    delta: Mapping[str, Any],
    model_type: type[BaseModel] | None = None,
) -> dict[str, Any]:
    merged = dict(base)
    for key, value in delta.items():
        annotation = _field_annotation(model_type, key)
        if (
            _is_dict_annotation(annotation)
            and isinstance(value, Mapping)
            and isinstance(merged.get(key), dict)
        ):
            merged[key] = _merge_dict_field(
                merged[key],
                value,
                _dict_value_model_type(annotation),
            )
            continue
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config_dict(
                merged[key],
                value,
                _model_type_from_annotation(annotation),
            )
            continue
        merged[key] = value
    return merged

def _save_config_file(
    config_to_save: AppConfig,
    file_path: str = DEFAULT_CONFIG_PATH,
    *,
    exclude_defaults: bool = True,
) -> None:
    path = Path(file_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config_to_save.model_dump(exclude_defaults=exclude_defaults), f, sort_keys=False)

def load_config(file_path: str = DEFAULT_CONFIG_PATH) -> AppConfig:
    """Loads config.yaml into a verified Pydantic object with env var lookups."""
    path = Path(file_path)
    if not path.exists():
        config = AppConfig()
        _save_config_file(config, file_path, exclude_defaults=False)
        return config

    with path.open("r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}

    return AppConfig.model_validate(config_data)


_config = load_config()


def get_config() -> AppConfig:
    return _config


def get_default_enabled_mcp_names(config: AppConfig | None = None) -> list[str]:
    current_config = get_config() if config is None else config
    return [
        name
        for name, server_config in get_config_path(current_config, "mcp").items()
        if server_config.enabled_by_default
    ]


def set_config(config: AppConfig) -> AppConfig:
    global _config
    _config = config
    return _config

def _is_sensitive_field(field: Any) -> bool:
    extra = field.json_schema_extra or {}
    return bool(extra.get(SENSITIVE_CONFIG_META_KEY))


def _field_model_class(field: Any) -> type[BaseModel] | None:
    return _model_type_from_annotation(field.annotation)


def _redact_value(value: Any) -> Any:
    if value in ("", None):
        return value
    return REDACTED_CONFIG_VALUE


def dump_public_config(
    model: BaseModel,
    model_cls: type[BaseModel] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    cls = model_cls or type(model)

    for name, field in cls.model_fields.items():
        value = getattr(model, name)
        nested_model_cls = _field_model_class(field)

        if _is_sensitive_field(field):
            result[name] = _redact_value(value)
        elif nested_model_cls is not None and isinstance(value, BaseModel):
            result[name] = dump_public_config(value, nested_model_cls)
        elif isinstance(value, list):
            result[name] = [
                dump_public_config(item) if isinstance(item, BaseModel) else item
                for item in value
            ]
        elif isinstance(value, dict):
            result[name] = {
                key: dump_public_config(item) if isinstance(item, BaseModel) else item
                for key, item in value.items()
            }
        else:
            result[name] = value

    return result

def strip_redacted_config_patch(
    delta: Mapping[str, Any],
    model_cls: type[BaseModel],
) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}

    for key, value in delta.items():
        field = model_cls.model_fields.get(key)
        if field is None:
            cleaned[key] = value
            continue

        nested_model_cls = _field_model_class(field)

        if _is_sensitive_field(field) and value == REDACTED_CONFIG_VALUE:
            continue

        if isinstance(value, Mapping) and nested_model_cls is not None:
            nested = strip_redacted_config_patch(
                value,
                nested_model_cls,
            )
            if nested:
                cleaned[key] = nested
        else:
            cleaned[key] = value

    return cleaned

def build_patched_config(
    delta: Mapping[str, Any],
    base_config: AppConfig | None = None,
) -> AppConfig:
    current_config = get_config() if base_config is None else base_config
    delta = strip_redacted_config_patch(delta, AppConfig)
    merged = _merge_config_dict(current_config.model_dump(), delta, AppConfig)
    return AppConfig.model_validate(merged)


def patch_config(delta: Mapping[str, Any]) -> AppConfig:
    """Apply a validated partial update to the live config."""
    return set_config(build_patched_config(delta))


def reload_config(file_path: str = DEFAULT_CONFIG_PATH) -> AppConfig:
    """Reload the live config from disk."""
    return set_config(load_config(file_path))


def save_config(config_to_save: AppConfig | None = None, file_path: str = DEFAULT_CONFIG_PATH):
    """Saves the Pydantic config object back to a YAML file."""
    current_config = get_config() if config_to_save is None else config_to_save
    _save_config_file(current_config, file_path, exclude_defaults=False)
