from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent.config import AppConfig


@dataclass(slots=True)
class RagPaths:
    root: Path
    raw_dir: Path
    cleaned_dir: Path
    chunks_dir: Path
    checkpoints_dir: Path


def get_rag_paths(config: AppConfig) -> RagPaths:
    root = Path(config.file.rag_path)

    raw_dir = root / "raw"
    cleaned_dir = root / "cleaned"
    chunks_dir = root / "chunks"
    checkpoints_dir = root / "checkpoints"

    for path in (root, raw_dir, cleaned_dir, chunks_dir, checkpoints_dir):
        path.mkdir(parents=True, exist_ok=True)

    return RagPaths(
        root=root,
        raw_dir=raw_dir,
        cleaned_dir=cleaned_dir,
        chunks_dir=chunks_dir,
        checkpoints_dir=checkpoints_dir,
    )
