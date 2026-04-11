import yaml
from pydantic import BaseModel
from typing import Optional, Literal
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

class AppConfig(BaseModel):
    api: ApiConfig
    file: FileConfig
    webfetch: WebFetchConfig
    websearch: WebSearchConfig

def load_config(file_path: str = "config.yaml") -> AppConfig:
    """Loads config.yaml into a verified Pydantic object with env var lookups."""
    with open(file_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}

    return AppConfig(**config_data)

def save_config(config: AppConfig, file_path: str = "config.yaml"):
    """Saves the Pydantic config object back to a YAML file."""
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config.model_dump(), f)


config = load_config()
