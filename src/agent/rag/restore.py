from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import aiosqlite
import orjson
import sqlite_vec

from agent.config import AppConfig
from agent.services.embedding_store import NAMESPACE, build_indexed_store


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
                await conn.execute(
                    """
                    INSERT OR REPLACE INTO store (
                        prefix, key, value, created_at, updated_at, expires_at, ttl_minutes
                    )
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL, NULL)
                    """,
                    (NAMESPACE, key, orjson.dumps(value)),
                )
                await conn.execute(
                    """
                    INSERT OR REPLACE INTO store_vectors (
                        prefix, key, field_name, embedding, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (
                        NAMESPACE,
                        key,
                        "retrieval_text",
                        sqlite_vec.serialize_float32(value["embedding"]),
                    ),
                )
                stats.added += 1
            except Exception:
                stats.failed += 1

        await conn.commit()

    return stats
