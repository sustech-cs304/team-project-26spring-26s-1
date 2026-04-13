from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

from agent.config import AppConfig, config as app_config
from scripts.rag.paths import get_rag_paths
from agent.tools.embedding_store import NAMESPACE, build_indexed_store, embed_texts


@dataclass(slots=True)
class EmbedStats:
    added: int = 0
    overwritten: int = 0
    failed: int = 0


def normalize_source_name(source: str) -> str:
    name = Path(str(source or "unknown")).name
    base = Path(name).stem
    for marker in (".cleaned", ".chunks"):
        if base.endswith(marker):
            base = base[: -len(marker)]
    return base or "unknown"


def _load_chunks_from_file(path: Path) -> list[dict]:
    chunks: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            chunks.append(json.loads(line))
    return chunks


def load_chunks(chunks_dir: Path, file_stem: str | None = None) -> list[dict]:
    files = sorted(chunks_dir.glob("*.jsonl"))
    if file_stem:
        files = [p for p in files if p.stem.startswith(file_stem)]

    chunks: list[dict] = []
    for jsonl_file in files:
        chunks.extend(_load_chunks_from_file(jsonl_file))
    return chunks


def _chunk_to_embedding_item(
    chunk: dict,
    source_file: str,
    chunk_index: int,
    embedding: list[float] | None = None,
) -> dict:
    text = str(chunk.get("text") or "")
    title_path = str(chunk.get("title_path") or "")
    retrieval_text = "\n".join([source_file, title_path, text])

    return {
        "source_file": source_file,
        "chunk_index": chunk_index,
        "text": text,
        "title_path": title_path,
        "retrieval_text": retrieval_text,
        "metadata": dict(chunk.get("metadata") or {}),
        "embedding": embedding if embedding is not None else chunk.get("embedding"),
    }


def chunks_to_embedding_items(chunks: list[dict]) -> list[dict]:
    embedding_items: list[dict] = []
    by_source_counter: dict[str, int] = {}

    for chunk in chunks:
        source = normalize_source_name(str(chunk.get("source_file") or "unknown"))
        if "chunk_index" in chunk:
            chunk_index = int(chunk.get("chunk_index", 0))
        else:
            chunk_index = by_source_counter.get(source, 0)
            by_source_counter[source] = chunk_index + 1

        embedding_items.append(
            _chunk_to_embedding_item(
                chunk,
                source_file=source,
                chunk_index=chunk_index,
                embedding=chunk.get("embedding"),
            )
        )

    return embedding_items


async def embed_chunks_to_json(config: AppConfig, chunks: list[dict], output_file: Path) -> dict[str, int]:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    failed = 0
    by_source: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunks:
        source = normalize_source_name(str(chunk.get("source_file") or "unknown"))
        by_source[source].append(chunk)

    embedding_items: list[dict] = []
    for source_file, source_chunks in by_source.items():
        missing_indices = [idx for idx, chunk in enumerate(source_chunks) if chunk.get("embedding") is None]
        missing_texts = [str(source_chunks[idx].get("text") or "") for idx in missing_indices]
        missing_vectors: list[list[float]] = []
        if missing_texts:
            missing_vectors = await embed_texts(missing_texts, config.api.embed)
        vectors_iter = iter(missing_vectors)

        for idx, chunk in enumerate(source_chunks):
            try:
                chunk_index = int(chunk.get("chunk_index", idx))
                embedding = chunk.get("embedding")
                if embedding is None:
                    embedding = next(vectors_iter)
                embedding_items.append(_chunk_to_embedding_item(chunk, source_file, chunk_index, embedding))
                total += 1
            except Exception:
                failed += 1

    with output_file.open("w", encoding="utf-8") as f:
        json.dump(embedding_items, f, ensure_ascii=False)

    return {
        "embedded": total,
        "failed": failed,
        "total_items": len(embedding_items),
    }


def load_embedding_array(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Embedding JSON must be an array of objects.")
    return [item for item in data if isinstance(item, dict)]


async def _clear_source_keys(conn: aiosqlite.Connection, source_file: str) -> int:
    cursor = await conn.execute(
        "DELETE FROM store WHERE prefix = ? AND key LIKE ?",
        (NAMESPACE, f"{source_file}#%"),
    )
    await conn.commit()
    return int(cursor.rowcount or 0)


async def restore_from_embedding_array(
    config: AppConfig,
    embedding_items: list[dict],
    store_db: Path,
    overwrite_sources: set[str] | None = None,
) -> EmbedStats:
    stats = EmbedStats()
    if not embedding_items:
        return stats

    overwrite_sources = {normalize_source_name(x) for x in (overwrite_sources or set())}

    async with aiosqlite.connect(str(store_db), isolation_level=None) as conn:
        indexed_store = build_indexed_store(type("Store", (), {"conn": conn})(), config.api.embed)
        await indexed_store.setup()

        for source_file in sorted(overwrite_sources):
            stats.overwritten += await _clear_source_keys(conn, source_file)

        for item in embedding_items:
            try:
                source_file = normalize_source_name(str(item.get("source_file") or "unknown"))
                chunk_index = int(item.get("chunk_index", 0))
                key = f"{source_file}#{chunk_index}"
                value = {
                    "text": str(item.get("text") or ""),
                    "title_path": str(item.get("title_path") or ""),
                    "retrieval_text": str(item.get("retrieval_text") or ""),
                    "source_file": source_file,
                    "chunk_index": chunk_index,
                    "metadata": dict(item.get("metadata") or {}),
                    "embedding": item.get("embedding"),
                }
                if not value["retrieval_text"]:
                    value["retrieval_text"] = "\n".join([source_file, value["title_path"], value["text"]])

                await indexed_store.aput((NAMESPACE,), key=key, value=value, index=["retrieval_text"])
                stats.added += 1
            except Exception:
                stats.failed += 1

    return stats


async def embed_and_restore(
    config: AppConfig,
    chunks: list[dict],
    store_db: Path,
    overwrite_sources: set[str] | None = None,
) -> EmbedStats:
    rag_paths = get_rag_paths(config)
    temp_json = rag_paths.embeddings_dir / "latest.embeddings.json"
    await embed_chunks_to_json(config=config, chunks=chunks, output_file=temp_json)

    embedding_items = load_embedding_array(temp_json)
    if overwrite_sources is None:
        overwrite_sources = {str(item.get("source_file") or "unknown") for item in embedding_items}

    return await restore_from_embedding_array(
        config=config,
        embedding_items=embedding_items,
        store_db=store_db,
        overwrite_sources=overwrite_sources,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split embedding and restore for rag vectors")
    parser.add_argument("--mode", choices=["embed", "restore", "both"], default="both")
    parser.add_argument("--chunks-dir", type=Path, default=None, help="Chunk jsonl directory")
    parser.add_argument("--file-stem", type=str, default=None, help="Only process chunk files by stem prefix")
    parser.add_argument("--output-json", type=Path, default=None, help="Embeddings JSON output file")
    parser.add_argument("--input-json", type=Path, default=None, help="Embeddings JSON input file")
    parser.add_argument("--store-db", type=Path, default=Path("agent_store.db"), help="SQLite store db path")
    parser.add_argument(
        "--overwrite-sources",
        type=str,
        default=None,
        help="Comma separated source_file names to clear before restore",
    )
    return parser.parse_args()


def _parse_overwrite_sources(raw: str | None) -> set[str] | None:
    if raw is None:
        return None
    parsed = {x.strip() for x in raw.split(",") if x.strip()}
    return parsed or None


async def _main_async() -> None:
    args = parse_args()
    rag_paths = get_rag_paths(app_config)

    chunks_dir = args.chunks_dir or rag_paths.chunks_dir
    output_json = args.output_json or (rag_paths.embeddings_dir / "latest.embeddings.json")
    overwrite_sources = _parse_overwrite_sources(args.overwrite_sources)

    if args.mode == "embed":
        chunks = load_chunks(chunks_dir=chunks_dir, file_stem=args.file_stem)
        stats = await embed_chunks_to_json(config=app_config, chunks=chunks, output_file=output_json)
        print(
            f"[embed] output={output_json} embedded={stats['embedded']} "
            f"failed={stats['failed']} total_items={stats['total_items']}"
        )
        return

    if args.mode == "restore":
        if args.input_json is None:
            raise ValueError("--input-json is required when mode=restore")
        embedding_items = load_embedding_array(args.input_json)
        if overwrite_sources is None:
            overwrite_sources = {str(item.get("source_file") or "unknown") for item in embedding_items}
        stats = await restore_from_embedding_array(
            config=app_config,
            embedding_items=embedding_items,
            store_db=args.store_db,
            overwrite_sources=overwrite_sources,
        )
        print(f"[restore] added={stats.added}, overwritten={stats.overwritten}, failed={stats.failed}")
        return

    chunks = load_chunks(chunks_dir=chunks_dir, file_stem=args.file_stem)
    embed_stats = await embed_chunks_to_json(config=app_config, chunks=chunks, output_file=output_json)
    embedding_items = load_embedding_array(output_json)
    if overwrite_sources is None:
        overwrite_sources = {str(item.get("source_file") or "unknown") for item in embedding_items}
    restore_stats = await restore_from_embedding_array(
        config=app_config,
        embedding_items=embedding_items,
        store_db=args.store_db,
        overwrite_sources=overwrite_sources,
    )
    print(
        f"[both] output={output_json} embedded={embed_stats['embedded']} "
        f"failed_embed={embed_stats['failed']} added={restore_stats.added} "
        f"overwritten={restore_stats.overwritten} failed_restore={restore_stats.failed}"
    )


def main() -> None:
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
