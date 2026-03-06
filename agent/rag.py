from __future__ import annotations

from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from qdrant_client import AsyncQdrantClient

from .config import Config
from .vectorstore import VectorStore

if TYPE_CHECKING:
    from .tools import ToolEntry


class KnowledgeBase:
    """Semantic search interface over the RAG knowledge-base qdrant collection.

    The collection is created automatically on first access if it does not yet
    exist. Use the `agent-ingest` CLI to populate it with document chunks.
    """

    def __init__(self, config: Config, client: AsyncOpenAI, qdrant: AsyncQdrantClient) -> None:
        self._config = config
        self._store = VectorStore(
            client=client,
            qdrant=qdrant,
            collection=config.rag_collection_name,
            embed_model=config.embed_model,
            embed_dims=config.embed_dims,
        )

    async def search(self, query: str, top_k: int | None = None) -> list[dict]:
        """Return the *top_k* most semantically relevant document chunks for *query*."""
        if top_k is None:
            top_k = self._config.rag_search_top_k
        results = await self._store.search(query, top_k)
        return [
            {
                "score": r["score"],
                "text": r["payload"].get("text", ""),
                "source": r["payload"].get("source", ""),
            }
            for r in results
        ]

    def get_tools(self) -> list[ToolEntry]:
        """Return knowledge-base tool entries for registration."""
        default_top_k = self._config.rag_search_top_k

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
                            f"Number of document chunks to retrieve. Default: {default_top_k}. "
                            "Increase (e.g. 10–15) for broad research questions where you want more coverage; "
                            "decrease (e.g. 1–3) for precise targeted lookups."
                        ),
                    },
                },
                "required": ["query"],
            },
        }

        async def _run(params: dict) -> str:
            results = await self.search(
                query=params["query"],
                top_k=params.get("top_k", default_top_k),
            )
            if not results:
                return "Knowledge base search returned no results."
            lines = []
            for i, r in enumerate(results, 1):
                source = f" [source: {r['source']}]" if r["source"] else ""
                lines.append(f"[{i}] (score={r['score']}){source}\n{r['text']}")
            return "\n\n".join(lines)

        return [(schema, _run)]
