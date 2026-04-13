from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from llama_index.core.ingestion import IngestionPipeline

from agent.config import AppConfig
from scripts.rag.clean_markdown import process_file as clean_one_file
from scripts.rag.clean_markdown import CleanStats
from scripts.rag.embedding_and_restore import (
    chunks_to_embedding_items,
    normalize_source_name,
    restore_from_embedding_array,
)
from scripts.rag.paths import get_rag_paths
from scripts.rag.partition import (
    PipelineOptions,
    build_ingestion_transformations,
    chunks_from_nodes,
    load_documents,
)


ALLOWED_SUFFIXES = {".txt", ".md", ".markdown"}


@dataclass(slots=True)
class RagPipelineResult:
    stored_file: Path
    cleaned_file: Path
    embeddings_json_file: Path
    chunks_count: int
    embedded_added: int
    embedded_overwritten: int
    embedded_failed: int


def ensure_allowed_text_file(file_name: str) -> str:
    safe_name = Path(file_name).name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_SUFFIXES))
        raise ValueError(f"Unsupported file type: {suffix}. Allowed: {allowed}")
    return safe_name


async def persist_upload_to_raw(upload: UploadFile, config: AppConfig) -> Path:
    rag_paths = get_rag_paths(config)
    safe_name = ensure_allowed_text_file(upload.filename or "uploaded.txt")
    target = rag_paths.raw_dir / safe_name
    content = await upload.read()
    target.write_bytes(content)
    return target


def _safe_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        # Best-effort cleanup should not fail the already completed restore path.
        pass


def cleanup_intermediate_files(
    *,
    raw_file: Path,
    cleaned_file: Path,
    embeddings_json_file: Path,
) -> None:
    _safe_unlink(raw_file)
    _safe_unlink(cleaned_file)
    _safe_unlink(embeddings_json_file)


async def run_rag_pipeline_for_file(
    raw_file: Path,
    config: AppConfig,
    store_db: Path,
    source_url: str | None = None,
) -> RagPipelineResult:
    rag_paths = get_rag_paths(config)

    clean_stats = CleanStats()
    clean_one_file(raw_file, rag_paths.cleaned_dir, suffix=".cleaned.md", stats=clean_stats)
    cleaned_file = rag_paths.cleaned_dir / f"{raw_file.stem}.cleaned.md"

    normalized_source_name = normalize_source_name(raw_file.stem)
    docs = load_documents(cleaned_file)
    pipeline = IngestionPipeline(
        transformations=build_ingestion_transformations(
            file_path=cleaned_file,
            options=PipelineOptions(),
            include_embedding=True,
        )
    )
    nodes = await asyncio.to_thread(pipeline.run, documents=docs)

    chunks = chunks_from_nodes(
        nodes,
        source_file=normalized_source_name,
        source_url=source_url,
    )
    chunks_count = len(chunks)

    embeddings_json_file = rag_paths.embeddings_dir / f"{raw_file.stem}.embeddings.json"
    embedding_items = chunks_to_embedding_items(chunks)
    with embeddings_json_file.open("w", encoding="utf-8") as f:
        json.dump(embedding_items, f, ensure_ascii=False)

    stats = await restore_from_embedding_array(
        config=config,
        embedding_items=embedding_items,
        store_db=store_db,
        overwrite_sources={normalized_source_name},
    )

    cleanup_intermediate_files(
        raw_file=raw_file,
        cleaned_file=cleaned_file,
        embeddings_json_file=embeddings_json_file,
    )
    
    _safe_unlink(rag_paths.root)

    return RagPipelineResult(
        stored_file=raw_file,
        cleaned_file=cleaned_file,
        embeddings_json_file=embeddings_json_file,
        chunks_count=chunks_count,
        embedded_added=stats.added,
        embedded_overwritten=stats.overwritten,
        embedded_failed=stats.failed,
    )
