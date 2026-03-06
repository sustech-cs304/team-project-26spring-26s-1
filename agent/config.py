"""
Central configuration for the agent, loaded from a YAML file.

Usage::

    cfg = Config.from_yaml()               # loads ./config.yaml (or defaults)
    cfg = Config.from_yaml("custom.yaml")  # loads a custom path
    cfg = Config()                          # pure-default config (no file)

Every module that needs configuration receives a ``Config`` instance via its
constructor — there are no module-level constants to import.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import tiktoken
import yaml
from jinja2 import Environment, FileSystemLoader


@dataclass
class Config:
    """Typed configuration object.  Instantiate via :meth:`from_yaml`."""

    # ── API: main agentic loop ───────────────────────────────────────
    agent_api_base_url: str = "https://coding.dashscope.aliyuncs.com/v1"
    agent_api_key: str | None = None
    agent_model: str = "qwen3.5-plus"

    # ── API: lightweight utility model ───────────────────────────────
    utility_api_base_url: str = "https://api.siliconflow.cn/v1"
    utility_api_key: str | None = None
    utility_model: str = "zai-org/GLM-4.6"

    # ── API: embedding model ─────────────────────────────────────────
    embed_api_base_url: str = "https://api.siliconflow.cn/v1"
    embed_api_key: str | None = None
    embed_model: str = "BAAI/bge-m3"
    embed_dims: int = 1024

    # ── Paths ────────────────────────────────────────────────────────
    data_dir: Path = field(default_factory=lambda: Path.cwd() / "data")
    skills_dir: Path = field(default_factory=lambda: Path.cwd() / "skills")

    # ── User identity ────────────────────────────────────────────────
    user_id: str = "user_123"

    # ── Core memory ──────────────────────────────────────────────────
    core_memory_token_limit: int = 400

    # ── Context / history management ─────────────────────────────────
    context_token_limit: int = 32_768
    fold_trigger_ratio: float = 0.70
    fold_fraction: float = 0.50

    # ── Archive conflict resolution ──────────────────────────────────
    archive_candidate_threshold: float = 0.70

    # ── RAG knowledge base ───────────────────────────────────────────
    rag_collection_name: str = "knowledge_base"
    rag_chunk_size: int = 200
    rag_chunk_overlap: int = 2
    rag_embed_batch_size: int = 32
    rag_search_top_k: int = 5

    # ── Skills store ─────────────────────────────────────────────────
    skills_collection_name: str = "skills"
    skills_search_top_k: int = 3

    # ── Code execution sandbox ───────────────────────────────────────
    sandbox_enabled: bool | None = None  # None → auto-detect at init time
    sandbox_image: str = "localhost/code_runner"
    sandbox_workdir_name: str = "sandbox_workspace"

    # ── Code execution security (local mode) ─────────────────────────
    code_security_review: bool = True
    code_security_autorun_low: bool = True

    # ── Derived resources (populated by __post_init__) ───────────────
    jinja_env: Environment = field(init=False, repr=False)
    tokenizer: tiktoken.Encoding = field(init=False, repr=False)

    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        # Resolve API keys from environment when not provided
        if self.agent_api_key is None:
            self.agent_api_key = os.getenv("AGENT_API_KEY")
        if self.utility_api_key is None:
            self.utility_api_key = os.getenv("UTILITY_API_KEY")
        if self.embed_api_key is None:
            self.embed_api_key = os.getenv("EMBED_API_KEY")

        # Auto-detect podman when sandbox_enabled was not explicitly set
        if self.sandbox_enabled is None:
            self.sandbox_enabled = self._detect_podman()

        # Shared Jinja2 template environment
        templates_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=False,
        )

        # Shared tokenizer (cl100k_base — GPT-4 / Qwen family)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    # ── Derived path properties ──────────────────────────────────────

    @property
    def mem0_qdrant_path(self) -> Path:
        return self.data_dir / "mem0_qdrant"

    @property
    def agent_qdrant_path(self) -> Path:
        return self.data_dir / "agent_qdrant"

    @property
    def core_memory_path(self) -> Path:
        return self.data_dir / "core_memory.json"

    # ── mem0 backend configuration dict ──────────────────────────────

    @property
    def mem0_config(self) -> dict:
        return {
            "llm": {
                "provider": "openai",
                "config": {
                    "openai_base_url": self.utility_api_base_url,
                    "api_key": self.utility_api_key,
                    "model": self.utility_model,
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "openai_base_url": self.embed_api_base_url,
                    "api_key": self.embed_api_key,
                    "model": self.embed_model,
                    "embedding_dims": self.embed_dims,
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "embedding_model_dims": self.embed_dims,
                    "path": str(self.mem0_qdrant_path),
                    "on_disk": True,
                },
            },
        }

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _detect_podman() -> bool:
        """Return True if podman-py is installed and the daemon is reachable."""
        try:
            import podman as _pm  # noqa: F401
            _pm.PodmanClient().version()
            return True
        except Exception:
            print(
                "Code execution sandbox disabled: "
                "podman-py not installed or daemon not running."
            )
            return False

    # ── Factory ──────────────────────────────────────────────────────

    @classmethod
    def from_yaml(cls, path: str | Path = "config.yaml") -> Config:
        """Load configuration from *path*, falling back to defaults.

        API keys that are ``null`` in the YAML (or absent) are resolved from
        the ``AGENT_API_KEY`` / ``UTILITY_API_KEY`` / ``EMBED_API_KEY``
        environment variables automatically.
        """
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path, encoding="utf-8") as fh:
            raw: dict = yaml.safe_load(fh) or {}

        kwargs: dict = {}

        # ── API sections ─────────────────────────────────────────────
        api = raw.get("api", {})
        for group, prefix in [("agent", "agent"), ("utility", "utility"), ("embed", "embed")]:
            section = api.get(group, {})
            if "base_url" in section:
                kwargs[f"{prefix}_api_base_url"] = section["base_url"]
            if "api_key" in section and section["api_key"] is not None:
                kwargs[f"{prefix}_api_key"] = section["api_key"]
            if "model" in section:
                kwargs[f"{prefix}_model"] = section["model"]
            if group == "embed" and "dims" in section:
                kwargs["embed_dims"] = section["dims"]

        # ── Paths ────────────────────────────────────────────────────
        paths_sec = raw.get("paths", {})
        for yaml_key, field_name in [("data_dir", "data_dir"), ("skills_dir", "skills_dir")]:
            if yaml_key in paths_sec:
                p = Path(paths_sec[yaml_key])
                kwargs[field_name] = p if p.is_absolute() else Path.cwd() / p

        # ── Simple 1:1 mappings ──────────────────────────────────────
        _MAP: dict[tuple[str, str], str] = {
            ("user", "id"):                       "user_id",
            ("core_memory", "token_limit"):        "core_memory_token_limit",
            ("context", "token_limit"):            "context_token_limit",
            ("context", "fold_trigger_ratio"):     "fold_trigger_ratio",
            ("context", "fold_fraction"):          "fold_fraction",
            ("archive", "candidate_threshold"):    "archive_candidate_threshold",
            ("rag", "collection_name"):            "rag_collection_name",
            ("rag", "chunk_size"):                 "rag_chunk_size",
            ("rag", "chunk_overlap"):              "rag_chunk_overlap",
            ("rag", "embed_batch_size"):           "rag_embed_batch_size",
            ("rag", "search_top_k"):               "rag_search_top_k",
            ("skills", "collection_name"):         "skills_collection_name",
            ("skills", "search_top_k"):            "skills_search_top_k",
            ("sandbox", "image"):                  "sandbox_image",
            ("sandbox", "workdir_name"):           "sandbox_workdir_name",
            ("security", "code_review"):           "code_security_review",
            ("security", "autorun_low"):           "code_security_autorun_low",
        }
        for (section, key), field_name in _MAP.items():
            val = raw.get(section, {}).get(key)
            if val is not None:
                kwargs[field_name] = val

        # ── sandbox.enabled: "auto"/null → None (auto-detect) ───────
        sandbox_raw = raw.get("sandbox", {}).get("enabled")
        if sandbox_raw is not None and sandbox_raw != "auto":
            kwargs["sandbox_enabled"] = bool(sandbox_raw)

        return cls(**kwargs)
