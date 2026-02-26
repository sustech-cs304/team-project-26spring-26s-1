"""
Central configuration for the agent.

All tuneable parameters live here. Changing a value here takes effect
everywhere in the codebase without touching individual modules.
"""

from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import tiktoken

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

API_BASE_URL: str = "https://api.siliconflow.cn/v1"

# Model used for the main agentic loop and out-of-band management calls
AGENT_MODEL: str = "Qwen/Qwen3-235B-A22B-Instruct-2507"

# ---------------------------------------------------------------------------
# Database paths
# ---------------------------------------------------------------------------

# Root directory that contains all persistent data stores. Can be overridden
# to an absolute path if you want the databases to live outside the project.
DATA_DIR: Path = Path.cwd() / "data"

# mem0's qdrant vector store (persistent local storage)
MEM0_QDRANT_PATH: Path = DATA_DIR / "mem0_qdrant"

# RAG knowledge-base qdrant store (populated via the agent-ingest CLI)
RAG_QDRANT_PATH: Path = DATA_DIR / "rag_qdrant"

# ---------------------------------------------------------------------------
# mem0 backend
# ---------------------------------------------------------------------------

MEM0_CONFIG: dict = {
    "llm": {
        "provider": "openai",
        "config": {
            "openai_base_url": API_BASE_URL,
            "model": "THUDM/glm-4-9b-chat",
        },
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "openai_base_url": API_BASE_URL,
            "model": "BAAI/bge-m3",
            "embedding_dims": 1024,
        },
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "embedding_model_dims": 1024,
            "path": str(MEM0_QDRANT_PATH),
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

# Embedding model and dimensions for the RAG store.
# Matches the mem0 embedder so that a single model handles both stores.
RAG_EMBED_MODEL: str = "BAAI/bge-m3"
RAG_EMBED_DIMS: int = 1024

# Ingestion chunking — word count per chunk; overlap is in *sentences* (not words)
RAG_CHUNK_SIZE: int = 200
RAG_CHUNK_OVERLAP: int = 2

# Number of texts sent per embedding API call during ingestion (batching)
RAG_EMBED_BATCH_SIZE: int = 32

# Default number of document chunks returned by the knowledge_base_search tool
RAG_SEARCH_TOP_K: int = 5

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
