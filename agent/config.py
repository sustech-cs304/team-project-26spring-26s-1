"""
Central configuration for the agent.

All tuneable parameters live here. Changing a value here takes effect
everywhere in the codebase without touching individual modules.
"""

import os

from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import tiktoken

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

# Main agentic loop
AGENT_API_BASE_URL: str = "https://coding.dashscope.aliyuncs.com/v1"
AGENT_API_KEY: str | None = os.getenv("AGENT_API_KEY")
AGENT_MODEL: str = "qwen3.5-plus"

# Lightweight model for cheap background maintenance tasks: mem0 internal LLM,
# security review of agent-generated code, conflict resolution, etc.
UTILITY_API_BASE_URL: str = "https://api.siliconflow.cn/v1"
UTILITY_API_KEY: str | None = os.getenv("UTILITY_API_KEY")
UTILITY_MODEL: str = "zai-org/GLM-4.6"

# Embedding model — used by both mem0's vector store and the RAG knowledge base.
# Must be the same model for both so that stored and query vectors are compatible.
EMBED_API_BASE_URL: str = "https://api.siliconflow.cn/v1"
EMBED_API_KEY: str | None = os.getenv("EMBED_API_KEY")
EMBED_MODEL: str = "BAAI/bge-m3"
EMBED_DIMS: int = 1024

# ---------------------------------------------------------------------------
# Database paths
# ---------------------------------------------------------------------------

# Root directory that contains all persistent data stores. Can be overridden
# to an absolute path if you want the databases to live outside the project.
DATA_DIR: Path = Path.cwd() / "data"

# mem0's qdrant vector store (persistent local storage)
MEM0_QDRANT_PATH: Path = DATA_DIR / "mem0_qdrant"

# Shared Qdrant database for all agent-owned vector stores (RAG, skills, …).
# One QdrantClient is opened per process and shared across all VectorStore
# instances — see main.py. ingest.py opens its own short-lived client on
# this same path because it runs as a separate process.
AGENT_QDRANT_PATH: Path = DATA_DIR / "agent_qdrant"

# Core memory persistence file — survives process restarts
CORE_MEMORY_PATH: Path = DATA_DIR / "core_memory.json"

# ---------------------------------------------------------------------------
# mem0 backend
# ---------------------------------------------------------------------------

MEM0_CONFIG: dict = {
    "llm": {
        "provider": "openai",
        "config": {
            "openai_base_url": UTILITY_API_BASE_URL,
            "api_key": UTILITY_API_KEY,
            "model": UTILITY_MODEL,
        },
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "openai_base_url": EMBED_API_BASE_URL,
            "api_key": EMBED_API_KEY,
            "model": EMBED_MODEL,
            "embedding_dims": EMBED_DIMS,
        },
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "embedding_model_dims": EMBED_DIMS,
            "path": str(MEM0_QDRANT_PATH),
            "on_disk": True,
        },
    },
}

# ---------------------------------------------------------------------------
# User identity
# ---------------------------------------------------------------------------

USER_ID: str = "user_123"

# ---------------------------------------------------------------------------
# Core memory
# ---------------------------------------------------------------------------

# Maximum tokens allowed in core memory before eviction is triggered
CORE_MEMORY_TOKEN_LIMIT: int = 400

# ---------------------------------------------------------------------------
# Context / history management
# ---------------------------------------------------------------------------

# Model context window size (tokens). Raise for models with larger windows.
CONTEXT_TOKEN_LIMIT: int = 32_768

# Fold is triggered when history token count reaches this fraction of CONTEXT_TOKEN_LIMIT
FOLD_TRIGGER_RATIO: float = 0.70

# Proportion of non-system messages to compress per fold pass
FOLD_FRACTION: float = 0.50

# ---------------------------------------------------------------------------
# Archive conflict resolution
# ---------------------------------------------------------------------------

# Cosine similarity floor for retrieving conflict candidates before the LLM
# agent makes the final keep/delete decision. Cast a wide net here.
ARCHIVE_CANDIDATE_THRESHOLD: float = 0.70

# ---------------------------------------------------------------------------
# RAG knowledge base
# ---------------------------------------------------------------------------

# Name of the qdrant collection used for externally-ingested documents
RAG_COLLECTION_NAME: str = "knowledge_base"

# Aliases for the central embedding constants — kept for backwards compatibility
# with rag.py and ingest.py which import these names.
RAG_EMBED_MODEL: str = EMBED_MODEL
RAG_EMBED_DIMS: int = EMBED_DIMS

# Ingestion chunking — word count per chunk; overlap is in *sentences* (not words)
RAG_CHUNK_SIZE: int = 200
RAG_CHUNK_OVERLAP: int = 2

# Number of texts sent per embedding API call during ingestion (batching)
RAG_EMBED_BATCH_SIZE: int = 32

# Default number of document chunks returned by the knowledge_base_search tool
RAG_SEARCH_TOP_K: int = 5

# ---------------------------------------------------------------------------
# Skills store
# ---------------------------------------------------------------------------

# Name of the qdrant collection used for agent-learned skill workflows.
# Lives in the shared agent_qdrant database alongside knowledge_base.
SKILLS_COLLECTION_NAME: str = "skills"

# Number of skills returned by skills_lookup
SKILLS_SEARCH_TOP_K: int = 3

# Root directory for on-disk skill files (VS Code agent convention).
# Each skill lives in skills/<name>/SKILL.md with optional references/ subdir.
SKILLS_DIR: Path = Path.cwd() / "skills"

# ---------------------------------------------------------------------------
# Code execution sandbox
# ---------------------------------------------------------------------------

def _detect_podman() -> bool:
    """Return True if podman-py is installed and the podman daemon is reachable."""
    try:
        import podman as _pm  # noqa: F401
        _pm.PodmanClient().version()
        return True
    except Exception:
        print("Code execution sandbox disabled: podman-py not installed or daemon not running.")
        return False

# Automatically True when podman-py is installed and the daemon is running.
# Override to False to force local mode even when podman is available.
SANDBOX_ENABLED: bool = _detect_podman()

# Podman image to use for the sandbox container
SANDBOX_IMAGE: str = "localhost/code_runner"

# Subdirectory of cwd that is bind-mounted into the container as /workspace.
# Host and container share this directory so files written inside the container
# are immediately accessible on the host and vice versa.
SANDBOX_WORKDIR_NAME: str = "sandbox_workspace"

# ---------------------------------------------------------------------------
# Code execution security (local / non-sandbox mode only)
# ---------------------------------------------------------------------------

# When True (and sandbox is False), UTILITY_MODEL reviews every Python/shell
# snippet before execution and the user must give explicit consent.
CODE_SECURITY_REVIEW: bool = True

# When True, snippets rated "low" risk are auto-approved without prompting.
# Set False to require explicit consent for every execution.
CODE_SECURITY_AUTORUN_LOW: bool = True

# ---------------------------------------------------------------------------
# Shared Jinja2 environment
# ---------------------------------------------------------------------------

TEMPLATES_DIR: Path = Path(__file__).parent / "templates"

jinja_env: Environment = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=False,
)

# ---------------------------------------------------------------------------
# Shared tokenizer
# ---------------------------------------------------------------------------

# cl100k_base is used by the GPT-4 / Qwen family and gives accurate token counts
tokenizer = tiktoken.get_encoding("cl100k_base")
