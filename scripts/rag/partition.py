from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.config import AppConfig, config as app_config

from llama_index.core import Document, SimpleDirectoryReader
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import (
    CodeSplitter,
    JSONNodeParser,
    MarkdownNodeParser,
    SemanticSplitterNodeParser,
    SentenceSplitter,
)


@dataclass(slots=True)
class RagPaths:
    root: Path
    raw_dir: Path
    cleaned_dir: Path
    chunks_dir: Path
    checkpoints_dir: Path
    embeddings_dir: Path


def get_rag_paths(config: AppConfig) -> RagPaths:
    root = Path(config.file.rag_path)

    raw_dir = root / "raw"
    cleaned_dir = root / "cleaned"
    chunks_dir = root / "chunks"
    checkpoints_dir = root / "checkpoints"
    embeddings_dir = root / "embeddings"

    for path in (root, raw_dir, cleaned_dir, chunks_dir, checkpoints_dir, embeddings_dir):
        path.mkdir(parents=True, exist_ok=True)

    return RagPaths(
        root=root,
        raw_dir=raw_dir,
        cleaned_dir=cleaned_dir,
        chunks_dir=chunks_dir,
        checkpoints_dir=checkpoints_dir,
        embeddings_dir=embeddings_dir,
    )


SUPPORTED_EXTS = {
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".jsonl",
    ".py",
    ".js",
    ".ts",
    ".java",
    ".cpp",
    ".c",
    ".go",
    ".rs",
    ".ipynb",
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".csv",
    ".html",
    ".xml",
}

CODE_EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".go": "go",
    ".rs": "rust",
}


@dataclass
class PipelineOptions:
    recursive_chunk_size: int = 800
    recursive_chunk_overlap: int = 120
    semantic_buffer_size: int = 1
    semantic_breakpoint_percentile_threshold: int = 95


_EMBED_MODEL = None
_EMBED_MODEL_READY = False


def collect_input_files(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        return []
    files = [p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]
    files.sort(key=lambda x: str(x))
    return files


def safe_rel_path(file_path: Path, base_dir: Path) -> str:
    try:
        return str(file_path.relative_to(base_dir))
    except Exception:
        return file_path.name


def sanitize_rel_for_output(rel_path: str) -> str:
    return rel_path.replace("\\", "__").replace("/", "__")


def get_embed_model() -> Any:
    global _EMBED_MODEL, _EMBED_MODEL_READY
    if _EMBED_MODEL_READY:
        return _EMBED_MODEL

    _EMBED_MODEL_READY = True
    try:
        from llama_index.embeddings.openai import OpenAIEmbedding

        embed_cfg = app_config.api.embed
        kwargs: dict[str, Any] = {
            "model_name": embed_cfg.model,
            "api_key": embed_cfg.api_key,
            "api_base": embed_cfg.base_url,
            "embed_batch_size": 64,
        }
        if getattr(embed_cfg, "dims", None):
            kwargs["dimensions"] = embed_cfg.dims

        try:
            _EMBED_MODEL = OpenAIEmbedding(**kwargs)
        except TypeError:
            kwargs.pop("dimensions", None)
            _EMBED_MODEL = OpenAIEmbedding(**kwargs)
        print(f"[信息] 嵌入模型已加载: {embed_cfg.model}")
    except Exception as exc:
        _EMBED_MODEL = None
        print(f"[警告] 嵌入模型加载失败: {exc}")
    return _EMBED_MODEL


def parser_for_file(file_path: Path) -> Any:
    suffix = file_path.suffix.lower()

    if suffix in {".md", ".markdown", ".txt"}:
        return MarkdownNodeParser.from_defaults()

    if suffix in {".json", ".jsonl"}:
        return JSONNodeParser.from_defaults()

    if suffix in CODE_EXT_TO_LANG:
        return CodeSplitter(
            language=CODE_EXT_TO_LANG[suffix],
            chunk_lines=60,
            chunk_lines_overlap=15,
            max_chars=1800,
        )

    return SentenceSplitter(chunk_size=1200, chunk_overlap=100)


def load_documents(file_path: Path) -> list[Document]:
    reader = SimpleDirectoryReader(input_files=[str(file_path)], required_exts=[file_path.suffix])
    return reader.load_data()


def build_ingestion_transformations(
    file_path: Path,
    options: PipelineOptions,
    *,
    include_embedding: bool,
    enable_semantic: bool = True,
) -> list[Any]:
    transformations: list[Any] = [
        parser_for_file(file_path),
        SentenceSplitter(
            chunk_size=options.recursive_chunk_size,
            chunk_overlap=options.recursive_chunk_overlap,
        ),
    ]

    embed_model = get_embed_model()
    if enable_semantic and embed_model is not None:
        transformations.append(
            SemanticSplitterNodeParser(
                embed_model=embed_model,
                buffer_size=options.semantic_buffer_size,
                breakpoint_percentile_threshold=options.semantic_breakpoint_percentile_threshold,
            )
        )

    if include_embedding:
        if embed_model is None:
            raise RuntimeError("Embedding model is not available; cannot run ingestion embedding stage.")
        transformations.append(embed_model)

    return transformations


def _extract_markdown_headings(text: str) -> list[tuple[int, str]]:
    headings: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("#"):
            continue
        level = len(line) - len(line.lstrip("#"))
        title = line[level:].strip()
        if title:
            headings.append((level, title))
    return headings


def _normalize_header_path(header_path: Any) -> list[str]:
    if not isinstance(header_path, str):
        return []
    return [part.strip() for part in header_path.split("/") if part.strip() and part.strip() != "/"]


def enrich_chunks_with_title_path(chunks: list[dict[str, Any]], source_file: str) -> list[dict[str, Any]]:
    heading_stack: list[str] = []
    enriched_chunks: list[dict[str, Any]] = []

    for chunk in chunks:
        text = str(chunk.get("text") or "")
        metadata = dict(chunk.get("metadata") or {})
        headings = _extract_markdown_headings(text)
        header_path_parts = _normalize_header_path(metadata.get("header_path"))

        if header_path_parts:
            heading_stack = header_path_parts.copy()

        if headings:
            for level, title in headings:
                while len(heading_stack) >= level:
                    heading_stack.pop()
                heading_stack.append(title)

        chunk_title_path = chunk.get("title_path")
        if not headings and isinstance(chunk_title_path, str) and chunk_title_path.strip():
            path_parts = [part.strip() for part in chunk_title_path.split("/") if part.strip() and part.strip() != "/"]
            if path_parts:
                heading_stack = path_parts

        title_path = " > ".join(heading_stack)
        retrieval_parts = [source_file]
        if title_path:
            retrieval_parts.append(title_path)
        retrieval_parts.append(text)
        retrieval_text = "\n".join(part for part in retrieval_parts if part)

        enriched = dict(chunk)
        metadata["title_path"] = title_path
        enriched["text"] = text
        enriched["metadata"] = metadata
        enriched["title_path"] = title_path
        enriched["retrieval_text"] = retrieval_text
        enriched_chunks.append(enriched)

    return enriched_chunks


def attach_source_url(chunks: list[dict[str, Any]], source_url: str | None) -> list[dict[str, Any]]:
    if not source_url:
        return chunks
    for chunk in chunks:
        metadata = dict(chunk.get("metadata") or {})
        metadata["source_url"] = source_url
        chunk["metadata"] = metadata
    return chunks


def chunks_from_nodes(nodes: list[Any], source_file: str, source_url: str | None = None) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for node in nodes:
        text = str(node.get_content() or "")
        if not text.strip():
            continue
        chunks.append(
            {
                "source_file": source_file,
                "text": text,
                "metadata": dict(getattr(node, "metadata", {}) or {}),
                "embedding": getattr(node, "embedding", None),
            }
        )

    enriched = enrich_chunks_with_title_path(chunks, source_file)
    return attach_source_url(enriched, source_url)


async def run_partition_for_file(
    file_path: Path,
    options: PipelineOptions,
    source_file: str,
    source_url: str | None = None,
) -> list[dict[str, Any]]:
    docs = load_documents(file_path)
    if not docs:
        return []

    pipeline = IngestionPipeline(
        transformations=build_ingestion_transformations(
            file_path=file_path,
            options=options,
            include_embedding=False,
        )
    )
    nodes = await asyncio.to_thread(pipeline.run, documents=docs)
    return chunks_from_nodes(nodes, source_file=source_file, source_url=source_url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="文档切分工具（无断点）")
    parser.add_argument("--input-file", type=str, default=None, help="仅切分单个文件")
    parser.add_argument("--input-dir", type=str, default=None, help="输入目录（覆盖默认 rag 路径）")
    parser.add_argument("--output-dir", type=str, default=None, help="输出目录（覆盖默认 rag 路径）")
    parser.add_argument("--recursive-chunk-size", type=int, default=800, help="递归切分 chunk 大小")
    parser.add_argument("--recursive-chunk-overlap", type=int, default=120, help="递归切分 overlap")
    parser.add_argument("--semantic-buffer-size", type=int, default=1, help="语义切分 buffer 大小")
    parser.add_argument(
        "--semantic-breakpoint-percentile-threshold",
        type=int,
        default=95,
        help="语义切分分位阈值",
    )
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    rag_paths = get_rag_paths(app_config)
    options = PipelineOptions(
        recursive_chunk_size=args.recursive_chunk_size,
        recursive_chunk_overlap=args.recursive_chunk_overlap,
        semantic_buffer_size=args.semantic_buffer_size,
        semantic_breakpoint_percentile_threshold=args.semantic_breakpoint_percentile_threshold,
    )

    input_dir = Path(args.input_dir) if args.input_dir else rag_paths.cleaned_dir
    output_dir = Path(args.output_dir) if args.output_dir else rag_paths.chunks_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print("文档切分工具（无断点）")
    print(f"输入目录: {input_dir}")
    print(f"输出目录: {output_dir}")

    if args.input_file:
        files = [Path(args.input_file)]
    else:
        files = collect_input_files(input_dir)

    if not files:
        print("[完成] 未发现可处理文件")
        return

    done = 0
    failed = 0
    total_chunks = 0

    for file_path in files:
        rel_path = safe_rel_path(file_path, input_dir)
        safe_name = sanitize_rel_for_output(rel_path)
        output_jsonl = output_dir / f"{safe_name}.chunks.jsonl"
        print(f"[处理] {rel_path}")

        try:
            chunks = await run_partition_for_file(
                file_path=file_path,
                options=options,
                source_file=file_path.stem,
                source_url=None,
            )
            with output_jsonl.open("w", encoding="utf-8") as f:
                for idx, chunk in enumerate(chunks):
                    payload = {
                        "source_file": file_path.stem,
                        "chunk_index": idx,
                        "text": chunk.get("text", ""),
                        "title_path": chunk.get("title_path", ""),
                        "retrieval_text": chunk.get("retrieval_text", chunk.get("text", "")),
                        "metadata": chunk.get("metadata", {}),
                    }
                    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            done += 1
            total_chunks += len(chunks)
            print(f"[完成] {rel_path} -> {output_jsonl}")
        except Exception as exc:
            failed += 1
            print(f"[失败] {rel_path}: {exc}")

    print("\n" + "=" * 56)
    print("[汇总] 文档切分完成")
    print("=" * 56)
    print(f"总数: {len(files)}")
    print(f"成功: {done}")
    print(f"失败: {failed}")
    print(f"chunks: {total_chunks}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
