"""
RAG knowledge-base interface.

Wraps a local qdrant collection containing externally-ingested document chunks
and exposes a semantic-search agent tool over that collection.

The knowledge base is populated out-of-band via the `agent-ingest` CLI tool
and is completely separate from the mem0 long-term memory store.
"""

from __future__ import annotations

import atexit
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from openai import OpenAI

from .config import (
    RAG_QDRANT_PATH,
    RAG_COLLECTION_NAME,
    RAG_EMBED_MODEL,
    RAG_EMBED_DIMS,
    RAG_SEARCH_TOP_K,
)
from .tools import Tools


class KnowledgeBase:
    """Semantic search interface over the RAG knowledge-base qdrant collection.

    The collection is created automatically on first access if it does not yet
    exist. Use the `agent-ingest` CLI to populate it with document chunks.
    """

    def __init__(self, client: OpenAI) -> None:
        self._client = client
        RAG_QDRANT_PATH.mkdir(parents=True, exist_ok=True)
        self._qdrant = QdrantClient(path=str(RAG_QDRANT_PATH))
        self._ensure_collection()
        atexit.register(self.close)

    def close(self) -> None:
        """Explicitly close the qdrant client, flushing any pending writes.

        Called by atexit so the flush happens while all library modules are
        still intact. Safe to call more than once.
        """
        try:
            self._qdrant.close()
        except Exception:
            pass

    def _ensure_collection(self) -> None:
        existing = {c.name for c in self._qdrant.get_collections().collections}
        if RAG_COLLECTION_NAME not in existing:
            self._qdrant.create_collection(
                collection_name=RAG_COLLECTION_NAME,
                vectors_config=VectorParams(size=RAG_EMBED_DIMS, distance=Distance.COSINE),
            )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=RAG_EMBED_MODEL, input=texts)
        return [r.embedding for r in response.data]

    def search(self, query: str, top_k: int = RAG_SEARCH_TOP_K) -> list[dict]:
        """Return the *top_k* most semantically relevant document chunks for *query*."""
        vec = self._embed([query])[0]
        hits = self._qdrant.query_points(
            collection_name=RAG_COLLECTION_NAME,
            query=vec,
            limit=top_k,
        ).points
        return [
            {
                "score": round(hit.score, 4),
                "text": hit.payload.get("text", ""),
                "source": hit.payload.get("source", ""),
            }
            for hit in hits
        ]

    def register_tools(self, tools: Tools) -> None:
        """Register the knowledge_base_search tool with the agent's tool registry."""

        schema = {
            "name": "knowledge_base_search",
            "description": (
                "Perform a semantic search over the RAG knowledge base — a curated collection of external documents "
                "and reference material that has been loaded by the operator using the agent-ingest command-line tool. "
                "This is entirely separate from long-term memory (which stores facts extracted from past conversations). "
                "Use this tool when the user asks a question that may be answered by documentation, manuals, notes, "
                "or any other reference documents that could have been ingested into the knowledge base. "
                "The search is purely semantic: write a descriptive natural-language query about the information you "
                "are looking for — not keywords. "
                "Each result includes the most relevant text passage, its source document label, and a relevance score. "
                "If the knowledge base is empty or contains nothing relevant, the tool will report that clearly. "
                "It is always worth trying this tool before answering factual questions about domain-specific topics, "
                "as the knowledge base may contain authoritative information the model would not otherwise know."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "A natural-language description of the information you want to find. "
                            "Be specific and descriptive rather than using single keywords. "
                            "Examples: 'step-by-step installation instructions for the authentication module', "
                            "'required fields in the user onboarding form', "
                            "'error handling strategy recommended for failed external API calls', "
                            "'company refund policy for subscription cancellations'."
                        ),
                    },
                    "top_k": {
                        "type": "integer",
                        "description": (
                            f"Number of document chunks to retrieve. Default: {RAG_SEARCH_TOP_K}. "
                            "Increase (e.g. 10–15) for broad research questions where you want more coverage; "
                            "decrease (e.g. 1–3) for precise targeted lookups."
                        ),
                    },
                },
                "required": ["query"],
            },
        }

        def _run(params: dict) -> str:
            results = self.search(
                query=params["query"],
                top_k=params.get("top_k", RAG_SEARCH_TOP_K),
            )
            if not results:
                return "Knowledge base search returned no results."
            lines = []
            for i, r in enumerate(results, 1):
                source = f" [source: {r['source']}]" if r["source"] else ""
                lines.append(f"[{i}] (score={r['score']}){source}\n{r['text']}")
            return "\n\n".join(lines)

        tools.add_tool(schema, _run)
