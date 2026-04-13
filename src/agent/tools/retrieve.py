from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import aiohttp

from langchain.tools import ToolRuntime, tool

from agent.services.embedding_store import NAMESPACE, build_indexed_store

from agent.config import get_config


@dataclass
class RankedResult:
    key: str
    value: dict[str, Any]
    score: float
    semantic_score: float
    rerank_score: float | None = None


def _dict_get_path(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    cur: Any = data
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
        if cur is None:
            return None
    return cur


def _build_embed_namespace(embed_dict: dict[str, Any] | None) -> Any:
    if not isinstance(embed_dict, dict) or not embed_dict:
        return None
    model = embed_dict.get("model")
    api_key = embed_dict.get("api_key")
    base_url = embed_dict.get("base_url")
    if not (model and api_key and base_url):
        return None
    return SimpleNamespace(
        model=model,
        api_key=api_key,
        base_url=base_url,
        dims=embed_dict.get("dims"),
    )


def _build_rerank_namespace(rerank_dict: dict[str, Any] | None) -> Any:
    if not isinstance(rerank_dict, dict) or not rerank_dict:
        return None
    model = rerank_dict.get("model")
    api_key = rerank_dict.get("api_key")
    base_url = rerank_dict.get("base_url")
    if not (model and api_key and base_url):
        return None
    return SimpleNamespace(
        model=model,
        api_key=api_key,
        base_url=base_url,
    )


def _extract_embed_from_candidate(candidate: Any) -> Any:
    if candidate is None:
        return None

    # Object shape: config.api.embed
    api_obj = getattr(candidate, "api", None)
    if api_obj is not None:
        embed_obj = getattr(api_obj, "embed", None)
        if embed_obj is not None:
            return embed_obj

    # Dict-like shapes used by RunnableConfig and web runtimes
    if isinstance(candidate, dict):
        for path in (
            ("api", "embed"),
            ("configurable", "api", "embed"),
            ("configurable", "config", "api", "embed"),
            ("__agent_config", "api", "embed"),
            ("configurable", "__agent_config", "api", "embed"),
            ("configurable", "app_config", "api", "embed"),
        ):
            embed_ns = _build_embed_namespace(_dict_get_path(candidate, path))
            if embed_ns is not None:
                return embed_ns

    return None


def _extract_rerank_from_candidate(candidate: Any) -> Any:
    if candidate is None:
        return None

    # Object shape: config.api.rerank
    api_obj = getattr(candidate, "api", None)
    if api_obj is not None:
        rerank_obj = getattr(api_obj, "rerank", None)
        if rerank_obj is not None:
            return rerank_obj

    # Dict-like shapes used by RunnableConfig and web runtimes
    if isinstance(candidate, dict):
        for path in (
            ("api", "rerank"),
            ("configurable", "api", "rerank"),
            ("configurable", "config", "api", "rerank"),
            ("__agent_config", "api", "rerank"),
            ("configurable", "__agent_config", "api", "rerank"),
            ("configurable", "app_config", "api", "rerank"),
        ):
            rerank_ns = _build_rerank_namespace(_dict_get_path(candidate, path))
            if rerank_ns is not None:
                return rerank_ns

    return None


def _resolve_embedding_config(runtime: ToolRuntime) -> Any:
    """Resolve embedding config from runtime or default config, supporting both object and dict shapes."""
    embed = _extract_embed_from_candidate(get_config())
    if embed is not None:
        return embed
    raise ValueError("Embedding config not found. Checked runtime.config/context and config.yaml in cwd/repository root.")


def _resolve_rerank_config(runtime: ToolRuntime) -> Any:
    """Resolve rerank config from runtime or default config, supporting both object and dict shapes."""
    rerank = _extract_rerank_from_candidate(get_config())
    if rerank is not None:
        return rerank
    raise ValueError("Rerank config not found. Checked runtime.config/context and config.yaml in cwd/repository root.")


def _build_rerank_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/rerank"


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_rerank_payload(payload: dict[str, Any]) -> list[tuple[int, float]]:
    candidates: list[tuple[int, float]] = []
    rows = payload.get("results")
    if not isinstance(rows, list):
        rows = payload.get("data")
    if not isinstance(rows, list):
        return candidates

    for row in rows:
        if not isinstance(row, dict):
            continue
        idx = row.get("index")
        if idx is None and isinstance(row.get("document"), dict):
            idx = row["document"].get("index")
        if not isinstance(idx, int):
            continue

        score = row.get("relevance_score")
        if score is None:
            score = row.get("score")
        candidates.append((idx, _to_float(score)))

    candidates.sort(key=lambda item: item[1], reverse=True)
    return candidates


async def _rerank_documents(query: str, documents: list[str], rerank_config: Any, top_k: int) -> list[tuple[int, float]]:
    if not documents:
        return []

    payload = {
        "model": rerank_config.model,
        "query": query,
        "documents": documents,
        "top_n": min(top_k, len(documents)),
    }

    headers = {
        "Authorization": f"Bearer {rerank_config.api_key}",
        "Content-Type": "application/json",
    }

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(_build_rerank_url(rerank_config.base_url), json=payload, headers=headers) as response:
            body = await response.text()
            if response.status >= 400:
                raise RuntimeError(f"Rerank request failed: status={response.status}, body={body[:400]}")
            try:
                data = await response.json()
            except Exception as exc:
                raise RuntimeError(f"Rerank response is not valid JSON: {body[:400]}") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Rerank response must be a JSON object.")

    return _parse_rerank_payload(data)


def _format_retrieve_results(results) -> str:
    if not results:
        return "No matching chunks found."

    lines = []
    for idx, item in enumerate(results, start=1):
        value = item.value or {}
        score = item.score
        text = value.get("text", "")
        source_file = value.get("source_file", "unknown")
        chunk_index = value.get("chunk_index", "unknown")
        semantic_score = getattr(item, "semantic_score", None)
        rerank_score = getattr(item, "rerank_score", None)
        score_text = f"{score:.6f}" if isinstance(score, (int, float)) else "unknown"
        semantic_text = f"{semantic_score:.6f}" if isinstance(semantic_score, (int, float)) else "unknown"
        rerank_text = f"{rerank_score:.6f}" if isinstance(rerank_score, (int, float)) else "unknown"

        metadata = value.get("metadata", {})
        source_url = metadata.get("source_url")
        lines.append(
            (
                f"{idx}. score={score_text} semantic={semantic_text} rerank={rerank_text} "
                f"source_url={source_url} "
                f"source={source_file} chunk={chunk_index} key={item.key}\n{text}"
            )
        )
    return "\n\n".join(lines)


@tool
async def retrieve_from_rag_db(runtime: ToolRuntime, query: str, top_k: int = 5) -> str:
    """Run semantic retrieval, rerank results with configured reranker, and return top-k chunks."""
    try:
        if not query or not query.strip():
            return "Error: Query must not be empty."
        if top_k <= 0:
            return "Error: top_k must be greater than 0."

        store = runtime.store
        if not store:
            return "Error: Store is not available from runtime."

        embedding_config = _resolve_embedding_config(runtime)
        rerank_config = _resolve_rerank_config(runtime)
        indexed_store = build_indexed_store(store, embedding_config)
        await indexed_store.setup()

        semantic_limit = max(top_k * 8, 40)
        semantic_results = await indexed_store.asearch(
            (NAMESPACE,),
            query=query,
            limit=semantic_limit,
        )

        semantic_candidates = [
            RankedResult(
                key=str(item.key),
                value=item.value or {},
                score=float(item.score),
                semantic_score=float(item.score),
            )
            for item in semantic_results
            if isinstance(getattr(item, "score", None), (int, float))
        ]

        if not semantic_candidates:
            return _format_retrieve_results([])

        documents = [
            str(candidate.value.get("retrieval_text") or candidate.value.get("text") or "")
            for candidate in semantic_candidates
        ]
        reranked_indices = await _rerank_documents(query, documents, rerank_config, top_k=top_k)

        if not reranked_indices:
            semantic_candidates.sort(key=lambda item: item.semantic_score, reverse=True)
            return _format_retrieve_results(semantic_candidates[:top_k])

        final_results: list[RankedResult] = []
        used_indices: set[int] = set()
        for idx, rerank_score in reranked_indices:
            if idx < 0 or idx >= len(semantic_candidates):
                continue
            candidate = semantic_candidates[idx]
            final_results.append(
                RankedResult(
                    key=candidate.key,
                    value=candidate.value,
                    score=rerank_score,
                    semantic_score=candidate.semantic_score,
                    rerank_score=rerank_score,
                )
            )
            used_indices.add(idx)
            if len(final_results) >= top_k:
                break

        if len(final_results) < top_k:
            remaining = [
                semantic_candidates[i]
                for i in range(len(semantic_candidates))
                if i not in used_indices
            ]
            remaining.sort(key=lambda item: item.semantic_score, reverse=True)
            for item in remaining[: top_k - len(final_results)]:
                final_results.append(
                    RankedResult(
                        key=item.key,
                        value=item.value,
                        score=item.semantic_score,
                        semantic_score=item.semantic_score,
                        rerank_score=None,
                    )
                )

        return _format_retrieve_results(final_results[:top_k])
    except Exception as exc:
        return f"Error: Failed to retrieve query results: {exc}"
