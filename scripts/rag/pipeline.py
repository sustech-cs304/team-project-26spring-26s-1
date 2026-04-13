from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from agent.config import AppConfig
from scripts.rag.clean_markdown import process_file as clean_one_file
from scripts.rag.clean_markdown import CleanStats
from scripts.rag.embedding_and_restore import (
    embed_chunks_to_json,
    load_embedding_array,
    normalize_source_name,
    restore_from_embedding_array,
)
from scripts.rag.paths import get_rag_paths


ALLOWED_SUFFIXES = {".txt", ".md", ".markdown"}


@dataclass(slots=True)
class RagPipelineResult:
    stored_file: Path
    cleaned_file: Path
    chunk_file: Path
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


def _chunk_file_for_source(chunks_dir: Path, source_rel_path: str) -> Path:
    safe_name = source_rel_path.replace("\\", "__").replace("/", "__")
    return chunks_dir / f"{safe_name}.chunks.jsonl"


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
    chunk_file: Path,
    checkpoint_file: Path,
    embeddings_json_file: Path,
) -> None:
    _safe_unlink(raw_file)
    _safe_unlink(cleaned_file)
    _safe_unlink(chunk_file)
    _safe_unlink(checkpoint_file)
    _safe_unlink(embeddings_json_file)


async def run_rag_pipeline_for_file(
    raw_file: Path,
    config: AppConfig,
    store_db: Path,
    source_url: str | None = None,
) -> RagPipelineResult:
    from scripts.rag.partition import partition_files

    rag_paths = get_rag_paths(config)

    clean_stats = CleanStats()
    clean_one_file(raw_file, rag_paths.cleaned_dir, suffix=".cleaned.md", stats=clean_stats)
    cleaned_file = rag_paths.cleaned_dir / f"{raw_file.stem}.cleaned.md"

    source_rel_path = str(cleaned_file.name)
    normalized_source_name = normalize_source_name(raw_file.stem)
    chunk_file = _chunk_file_for_source(rag_paths.chunks_dir, source_rel_path)
    checkpoint_file = rag_paths.checkpoints_dir / f"{raw_file.stem}.partition_checkpoint.json"

    # Overwrite strategy: clear old partition artifacts and rebuild chunks.
    if chunk_file.exists():
        chunk_file.unlink()
    if checkpoint_file.exists():
        checkpoint_file.unlink()

    partition_result = await partition_files(
        files=[cleaned_file],
        input_dir=rag_paths.cleaned_dir,
        output_dir=rag_paths.chunks_dir,
        checkpoint_file=checkpoint_file,
        source_url=source_url,
    )

    chunks_count = int(partition_result.get("chunks", 0))

    chunks = []
    if chunk_file.exists():
        with chunk_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    payload = json.loads(line)
                    payload["source_file"] = normalized_source_name
                    chunks.append(payload)

    embeddings_json_file = rag_paths.embeddings_dir / f"{raw_file.stem}.embeddings.json"
    await embed_chunks_to_json(
        config=config,
        chunks=chunks,
        output_file=embeddings_json_file,
    )
    embedding_items = load_embedding_array(embeddings_json_file)

    stats = await restore_from_embedding_array(
        config=config,
        embedding_items=embedding_items,
        store_db=store_db,
        overwrite_sources={normalized_source_name},
    )

    cleanup_intermediate_files(
        raw_file=raw_file,
        cleaned_file=cleaned_file,
        chunk_file=chunk_file,
        checkpoint_file=checkpoint_file,
        embeddings_json_file=embeddings_json_file,
    )
    
    _safe_unlink(rag_paths.root)

    return RagPipelineResult(
        stored_file=raw_file,
        cleaned_file=cleaned_file,
        chunk_file=chunk_file,
        embeddings_json_file=embeddings_json_file,
        chunks_count=chunks_count,
        embedded_added=stats.added,
        embedded_overwritten=stats.overwritten,
        embedded_failed=stats.failed,
    )
