import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from langchain.tools import ToolRuntime, tool

from .embedding_store import NAMESPACE, build_indexed_store
from agent.config import load_config


@dataclass
class RankedResult:
    key: str
    value: dict[str, Any]
    score: float
    semantic_score: float
    lexical_score: float


@dataclass(slots=True)
class QueryAnalysis:
    normalized_query: str
    terms: list[str]
    intent_terms: list[str]


@dataclass(slots=True)
class CorpusChunk:
    key: str
    value: dict[str, Any]
    text: str
    retrieval_text: str
    title_path: str
    source_file: str
    chunk_index: Any


_CORPUS_CACHE: dict[int, tuple[int, list[CorpusChunk]]] = {}


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


def _resolve_embedding_config(runtime: ToolRuntime) -> Any:
    """Resolve embedding config from runtime or default config, supporting both object and dict shapes."""
    runtime_config = getattr(runtime, "config", None)
    embed = _extract_embed_from_candidate(runtime_config)
    if embed is not None:
        return embed

    runtime_context = getattr(runtime, "context", None)
    embed = _extract_embed_from_candidate(runtime_context)
    if embed is not None:
        return embed

    # Fallback 1: default loader (depends on process cwd)
    try:
        app_config = load_config()
        embed = _extract_embed_from_candidate(app_config)
        if embed is not None:
            return embed
    except Exception:
        pass

    # Fallback 2: absolute path from repository root
    repo_config_path = Path(__file__).resolve().parents[3] / "config.yaml"
    try:
        app_config = load_config(str(repo_config_path))
        embed = _extract_embed_from_candidate(app_config)
        if embed is not None:
            return embed
    except Exception:
        pass

    raise ValueError(
        "Embedding config not found. Checked runtime.config/context and config.yaml in cwd/repository root."
    )


def _normalize_query_text(query: str) -> str:
    text = query.strip().lower()
    text = re.sub(r"[\s\u3000]+", "", text)
    text = re.sub(r"[，。！？、；：,.!?;:()（）【】\[\]<>《》\"'“”‘’]", "", text)
    for ch in "的了和与及是吗呢吧啊呀哦嘛请问什么哪些如何怎么是否可能可以需要想要请教一下有关关于相关方面":
        text = text.replace(ch, "")
    return text


def _extract_terms_from_cjk_sequence(sequence: str) -> list[str]:
    if len(sequence) <= 2:
        return [sequence]

    max_n = min(5, len(sequence))
    terms: list[str] = []
    for n in range(max_n, 1, -1):
        for start in range(0, len(sequence) - n + 1):
            term = sequence[start : start + n]
            if term and term not in terms:
                terms.append(term)
    return terms


def _analyze_query(query: str, max_terms: int = 30) -> QueryAnalysis:
    normalized_query = _normalize_query_text(query)
    if not normalized_query:
        return QueryAnalysis(normalized_query="", terms=[], intent_terms=[])

    intent_terms = [
        term
        for term in ("流程", "步骤", "条件", "标准", "办法", "规定", "要求", "资格", "程序", "申请", "评选", "名单")
        if term in normalized_query
    ]

    terms: list[str] = []
    for token in re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]+", normalized_query):
        if re.fullmatch(r"[a-z0-9_]{2,}", token):
            if token not in terms:
                terms.append(token)
        else:
            for extracted in _extract_terms_from_cjk_sequence(token):
                if extracted not in terms:
                    terms.append(extracted)
                if len(terms) >= max_terms:
                    break
        if len(terms) >= max_terms:
            break

    for intent_term in intent_terms:
        if intent_term not in terms:
            terms.insert(0, intent_term)

    deduped: list[str] = []
    for term in terms:
        if term and term not in deduped:
            deduped.append(term)
        if len(deduped) >= max_terms:
            break

    return QueryAnalysis(normalized_query=normalized_query, terms=deduped, intent_terms=intent_terms)


def _to_text(payload_value: Any) -> str:
    if isinstance(payload_value, bytes):
        try:
            return payload_value.decode("utf-8")
        except UnicodeDecodeError:
            return payload_value.decode("utf-8", errors="ignore")
    if isinstance(payload_value, str):
        return payload_value
    return ""


def _normalize_scores(raw_scores: dict[str, float]) -> dict[str, float]:
    if not raw_scores:
        return {}
    values = list(raw_scores.values())
    score_min = min(values)
    score_max = max(values)
    if score_max == score_min:
        return {k: 1.0 for k in raw_scores}
    return {k: (v - score_min) / (score_max - score_min) for k, v in raw_scores.items()}


def _term_weight(term: str) -> float:
    if len(term) >= 5:
        return 2.0
    if len(term) == 4:
        return 1.6
    if len(term) == 3:
        return 1.3
    if term in {"流程", "条件", "标准", "办法", "规定", "申请", "评选", "程序", "资格", "步骤", "名单"}:
        return 1.1
    return 0.9


def _looks_like_toc_chunk(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 12:
        return False
    page_num_like = 0
    for line in lines:
        if re.search(r"\d{1,4}$", line):
            page_num_like += 1
    return page_num_like >= 6


def _looks_like_cover_chunk(text: str, title_path: str, chunk_index: Any) -> bool:
    if title_path:
        return False

    stripped = text.strip()
    if not stripped:
        return True

    if str(chunk_index) == "0":
        return len(stripped) <= 80

    tokens = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", stripped)
    if len(stripped) <= 60 and len(tokens) <= 4:
        return True

    if stripped.upper() == stripped and len(stripped) <= 80:
        return True

    return False


def _chunk_noise_factor(text: str, title_path: str, chunk_index: Any) -> float:
    factor = 1.0

    if _looks_like_toc_chunk(text):
        factor *= 0.35

    if _looks_like_cover_chunk(text, title_path, chunk_index):
        factor *= 0.1

    stripped = text.strip()
    if title_path and len(stripped) <= 24:
        factor *= 0.6

    if title_path and len(title_path.split(" > ")) == 1 and len(stripped) <= 80:
        factor *= 0.85

    return factor


def _parse_corpus_chunk(key: str, payload: dict[str, Any]) -> CorpusChunk | None:
    source_file = str(payload.get("source_file") or "")
    chunk_index = payload.get("chunk_index")
    text = str(payload.get("text") or "")
    retrieval_text = str(payload.get("retrieval_text") or text)
    title_path = str(payload.get("title_path") or "")
    if not source_file or not retrieval_text:
        return None
    return CorpusChunk(
        key=key,
        value=payload,
        text=text,
        retrieval_text=retrieval_text,
        title_path=title_path,
        source_file=source_file,
        chunk_index=chunk_index,
    )


async def _load_corpus(runtime_store: Any) -> list[CorpusChunk]:
    if not hasattr(runtime_store, "conn") or runtime_store.conn is None:
        return []

    conn = runtime_store.conn
    conn_id = id(conn)
    row_count_row = await conn.execute("SELECT COUNT(*) FROM store")
    row_count = (await row_count_row.fetchone())[0]
    await row_count_row.close()

    cached = _CORPUS_CACHE.get(conn_id)
    if cached and cached[0] == row_count:
        return cached[1]

    cursor = await conn.execute("SELECT key, value FROM store")
    rows = await cursor.fetchall()
    await cursor.close()

    corpus: list[CorpusChunk] = []
    for key, raw_value in rows:
        payload_text = _to_text(raw_value)
        if not payload_text:
            continue
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        chunk = _parse_corpus_chunk(str(key), payload)
        if chunk is not None:
            corpus.append(chunk)

    _CORPUS_CACHE[conn_id] = (row_count, corpus)
    return corpus


async def _lexical_recall(runtime_store: Any, analysis: QueryAnalysis, limit: int) -> list[tuple[str, dict[str, Any], float]]:
    if not analysis.terms:
        return []
    corpus = await _load_corpus(runtime_store)
    if not corpus:
        return []

    term_weights = {term: _term_weight(term) for term in analysis.terms}
    total_weight = sum(term_weights.values()) or 1.0

    recalled: list[tuple[str, dict[str, Any], float]] = []
    for chunk in corpus:
        retrieval_text = chunk.retrieval_text
        title_path = chunk.title_path
        source_file = chunk.source_file
        hit_weight = 0.0
        title_weight = 0.0
        source_weight = 0.0

        for term, weight in term_weights.items():
            if term in retrieval_text:
                hit_weight += weight
            if title_path and term in title_path:
                title_weight += weight
            if term in source_file:
                source_weight += weight * 0.25

        query_phrase = analysis.normalized_query
        phrase_boost = 0.8 if query_phrase and query_phrase in retrieval_text else 0.0
        title_boost = 0.5 if query_phrase and query_phrase in title_path else 0.0
        lexical_score = (hit_weight / total_weight) + 0.35 * (title_weight / total_weight) + source_weight + phrase_boost + title_boost

        lexical_score *= _chunk_noise_factor(retrieval_text, title_path, chunk.chunk_index)

        if lexical_score <= 0:
            continue
        recalled.append((chunk.key, chunk.value, float(lexical_score)))

    recalled.sort(key=lambda x: x[2], reverse=True)
    return recalled[:limit]


def _hybrid_rerank(
    semantic_results,
    lexical_results: list[tuple[str, dict[str, Any], float]],
    top_k: int,
) -> list[RankedResult]:
    semantic_raw = {
        str(item.key): float(item.score)
        for item in semantic_results
        if isinstance(item.score, (int, float))
    }
    lexical_raw = {key: score for key, _, score in lexical_results}

    semantic_norm = _normalize_scores(semantic_raw)
    lexical_norm = _normalize_scores(lexical_raw)

    value_by_key: dict[str, dict[str, Any]] = {}
    for item in semantic_results:
        value_by_key[str(item.key)] = item.value or {}
    for key, value, _ in lexical_results:
        value_by_key.setdefault(key, value)

    merged_keys = set(value_by_key.keys())
    has_lexical_hits = any(v > 0 for v in lexical_norm.values())
    reranked: list[RankedResult] = []
    for key in merged_keys:
        s = semantic_norm.get(key, 0.0)
        l = lexical_norm.get(key, 0.0)
        value = value_by_key.get(key, {})
        text = str(value.get("text") or "")
        title_path = str(value.get("title_path") or "")
        retrieval_text = str(value.get("retrieval_text") or text)
        source_file = str(value.get("source_file") or "")

        # semantic 主导，lexical 兜底，提高通用检索稳定性
        if s > 0 and l > 0:
            final = 0.45 * s + 0.55 * l if has_lexical_hits else 0.7 * s + 0.3 * l
        elif s > 0:
            final = 0.6 * s if has_lexical_hits else 0.85 * s
        else:
            final = 0.75 * l

        if title_path:
            final += min(len(title_path.split(" > ")) * 0.015, 0.06)

        if source_file:
            final += 0.02 if source_file.endswith(".md") else 0.0

        final *= _chunk_noise_factor(text, title_path, value.get("chunk_index"))

        if query_phrase := _normalize_query_text(" ".join(str(v) for v in [title_path, retrieval_text])):
            if query_phrase and query_phrase in retrieval_text:
                final += 0.05

        reranked.append(
            RankedResult(
                key=key,
                value=value,
                score=float(final),
                semantic_score=float(s),
                lexical_score=float(l),
            )
        )

    reranked.sort(key=lambda x: x.score, reverse=True)
    return reranked[:top_k]


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
        lexical_score = getattr(item, "lexical_score", None)
        score_text = f"{score:.6f}" if isinstance(score, (int, float)) else "unknown"
        semantic_text = f"{semantic_score:.6f}" if isinstance(semantic_score, (int, float)) else "unknown"
        lexical_text = f"{lexical_score:.6f}" if isinstance(lexical_score, (int, float)) else "unknown"
        lines.append(
            (
                f"{idx}. score={score_text} semantic={semantic_text} lexical={lexical_text} "
                f"source={source_file} chunk={chunk_index} key={item.key}\n{text}"
            )
        )
    return "\n\n".join(lines)


@tool
async def retrieve_from_rag_db(runtime: ToolRuntime, query: str, top_k: int = 5) -> str:
    """Run hybrid retrieval (semantic + lexical recall) and rerank candidates to return top-k chunks."""
    try:
        if not query or not query.strip():
            return "Error: Query must not be empty."
        if top_k <= 0:
            return "Error: top_k must be greater than 0."

        store = runtime.store
        if not store:
            return "Error: Store is not available from runtime."

        embedding_config = _resolve_embedding_config(runtime)
        indexed_store = build_indexed_store(store, embedding_config)
        await indexed_store.setup()

        semantic_limit = max(top_k * 8, 40)
        lexical_limit = max(top_k * 10, 80)

        analysis = _analyze_query(query)
        semantic_results = await indexed_store.asearch(
            (NAMESPACE,),
            query=query,
            limit=semantic_limit,
        )

        lexical_results = await _lexical_recall(store, analysis, limit=lexical_limit)
        reranked_results = _hybrid_rerank(semantic_results, lexical_results, top_k=top_k)
        return _format_retrieve_results(reranked_results)
    except Exception as exc:
        return f"Error: Failed to retrieve query results: {exc}"