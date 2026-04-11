from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

from agent.config import AppConfig, config as app_config
from agent.rag.paths import get_rag_paths
from agent.tools.embedding_store import NAMESPACE, build_indexed_store, embed_texts


@dataclass(slots=True)
class EmbedStats:
    added: int = 0
    overwritten: int = 0
    failed: int = 0


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


async def _clear_source_keys(conn: aiosqlite.Connection, source_file: str) -> int:
    # Store namespace in sqlite uses dot-joined prefix text (e.g. embeddings).
    cursor = await conn.execute(
        "DELETE FROM store WHERE prefix = ? AND key LIKE ?",
        (NAMESPACE, f"{source_file}#%"),
    )
    await conn.commit()
    return int(cursor.rowcount or 0)


async def embed_and_restore(
    config: AppConfig,
    chunks: list[dict],
    store_db: Path,
    overwrite_sources: set[str] | None = None,
) -> EmbedStats:
    stats = EmbedStats()
    if not chunks:
        return stats

    overwrite_sources = overwrite_sources or set()

    async with aiosqlite.connect(str(store_db), isolation_level=None) as conn:
        indexed_store = build_indexed_store(type("Store", (), {"conn": conn})(), config.api.embed)
        await indexed_store.setup()

        for source_file in sorted(overwrite_sources):
            stats.overwritten += await _clear_source_keys(conn, source_file)

        by_source: dict[str, list[dict]] = defaultdict(list)
        for chunk in chunks:
            source = str(chunk.get("source_file") or "unknown")
            by_source[source].append(chunk)

        for source_file, source_chunks in by_source.items():
            texts = [str(chunk.get("text") or "") for chunk in source_chunks]
            vectors = await embed_texts(texts, config.api.embed)

            for chunk, embedding in zip(source_chunks, vectors):
                try:
                    chunk_index = int(chunk.get("chunk_index", 0))
                    key = f"{source_file}#{chunk_index}"
                    value = {
                        "text": str(chunk.get("text") or ""),
                        "title_path": str(chunk.get("title_path") or ""),
                        "retrieval_text": str(chunk.get("retrieval_text") or ""),
                        "source_file": source_file,
                        "chunk_index": chunk_index,
                        "metadata": dict(chunk.get("metadata") or {}),
                        "embedding": embedding,
                    }
                    if not value["retrieval_text"]:
                        value["retrieval_text"] = "\n".join(
                            [
                                source_file,
                                value["title_path"],
                                value["text"],
                            ]
                        )

                    await indexed_store.aput((NAMESPACE,), key=key, value=value, index=["retrieval_text"])
                    stats.added += 1
                except Exception:
                    stats.failed += 1
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed chunks and restore into agent_store.db")
    parser.add_argument("--chunks-dir", type=Path, default=None, help="Chunk jsonl directory")
    parser.add_argument("--store-db", type=Path, default=Path("agent_store.db"), help="SQLite store db path")
    parser.add_argument("--file-stem", type=str, default=None, help="Only process chunk files by stem prefix")
    return parser.parse_args()


async def _main_async() -> None:
    args = parse_args()
    rag_paths = get_rag_paths(app_config)
    chunks_dir = args.chunks_dir or rag_paths.chunks_dir
    chunks = load_chunks(chunks_dir=chunks_dir, file_stem=args.file_stem)
    stats = await embed_and_restore(config=app_config, chunks=chunks, store_db=args.store_db)
    print(f"[embedding] added={stats.added}, overwritten={stats.overwritten}, failed={stats.failed}")


def main() -> None:
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
