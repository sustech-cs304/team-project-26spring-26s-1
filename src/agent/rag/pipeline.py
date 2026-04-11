from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from agent.config import AppConfig
from agent.rag.clean_markdown import process_file as clean_one_file
from agent.rag.clean_markdown import CleanStats
from agent.rag.embedding_and_restore import embed_and_restore
from agent.rag.paths import get_rag_paths


ALLOWED_SUFFIXES = {".txt", ".md", ".markdown"}


@dataclass(slots=True)
class RagPipelineResult:
    stored_file: Path
    cleaned_file: Path
    chunk_file: Path
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


async def run_rag_pipeline_for_file(
    raw_file: Path,
    config: AppConfig,
    store_db: Path,
    source_url: str | None = None,
) -> RagPipelineResult:
    from agent.rag.partition_langgraph import partition_files

    rag_paths = get_rag_paths(config)

    clean_stats = CleanStats()
    clean_one_file(raw_file, rag_paths.cleaned_dir, suffix=".cleaned.md", stats=clean_stats)
    cleaned_file = rag_paths.cleaned_dir / f"{raw_file.stem}.cleaned.md"

    source_rel_path = str(cleaned_file.name)
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
                    chunks.append(json.loads(line))

    stats = await embed_and_restore(
        config=config,
        chunks=chunks,
        store_db=store_db,
        overwrite_sources={source_rel_path},
    )

    return RagPipelineResult(
        stored_file=raw_file,
        cleaned_file=cleaned_file,
        chunk_file=chunk_file,
        chunks_count=chunks_count,
        embedded_added=stats.added,
        embedded_overwritten=stats.overwritten,
        embedded_failed=stats.failed,
    )
