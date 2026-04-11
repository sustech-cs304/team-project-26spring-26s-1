from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, StateGraph

from agent.config import config as app_config
from agent.rag.paths import get_rag_paths

from llama_index.core import Document, SimpleDirectoryReader
from llama_index.core.node_parser import (
    CodeSplitter,
    JSONNodeParser,
    LangchainNodeParser,
    MarkdownNodeParser,
    SemanticSplitterNodeParser,
    SentenceSplitter,
)


os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

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


class ChunkGraphState(TypedDict):
    input_dir: str
    output_dir: str
    checkpoint_file: str
    all_files: List[str]
    done_files: List[str]
    failed_files: List[str]
    skipped_files: List[str]


class FileGraphState(TypedDict):
    file_path: str
    input_dir: str
    output_dir: str
    checkpoint_file: str
    result: str


@dataclass
class PipelineOptions:
    recursive_chunk_size: int = 800
    recursive_chunk_overlap: int = 120
    semantic_buffer_size: int = 1
    semantic_breakpoint_percentile_threshold: int = 95


_EMBED_MODEL = None
_EMBED_MODEL_READY = False
CHECKPOINT_LOCK = asyncio.Lock()


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_rel_path(file_path: Path, base_dir: Path) -> str:
    try:
        return str(file_path.relative_to(base_dir))
    except Exception:
        return file_path.name


def sanitize_rel_for_output(rel_path: str) -> str:
    return rel_path.replace("\\", "__").replace("/", "__")


def load_checkpoint(checkpoint_file: Path) -> Dict[str, Any]:
    if not checkpoint_file.exists():
        return {"version": 1, "updated_at": now_str(), "documents": {}}

    with checkpoint_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    data.setdefault("version", 1)
    data.setdefault("updated_at", now_str())
    data.setdefault("documents", {})
    return data


def save_checkpoint(checkpoint_file: Path, checkpoint_data: Dict[str, Any]) -> None:
    checkpoint_data["updated_at"] = now_str()
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint_file.open("w", encoding="utf-8") as f:
        json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)


def collect_input_files(input_dir: Path) -> List[Path]:
    if not input_dir.exists():
        return []
    files = [p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]
    files.sort(key=lambda x: str(x))
    return files


def get_embed_model() -> Any:
    global _EMBED_MODEL, _EMBED_MODEL_READY
    if _EMBED_MODEL_READY:
        return _EMBED_MODEL

    _EMBED_MODEL_READY = True
    try:
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        _EMBED_MODEL = HuggingFaceEmbedding(model_name="BAAI/bge-small-zh-v1.5")
        print("[信息] 语义切分嵌入模型已加载：BAAI/bge-small-zh-v1.5")
    except Exception as exc:
        _EMBED_MODEL = None
        print(f"[警告] 语义切分模型加载失败，将退化到非语义切分: {exc}")
    return _EMBED_MODEL


def parse_by_format(file_path: Path, documents: List[Document]) -> List[Any]:
    suffix = file_path.suffix.lower()

    if suffix in {".md", ".markdown"}:
        parser = MarkdownNodeParser.from_defaults()
        return parser.get_nodes_from_documents(documents)

    if suffix in {".json", ".jsonl"}:
        parser = JSONNodeParser.from_defaults()
        return parser.get_nodes_from_documents(documents)

    if suffix in CODE_EXT_TO_LANG:
        parser = CodeSplitter(
            language=CODE_EXT_TO_LANG[suffix],
            chunk_lines=60,
            chunk_lines_overlap=15,
            max_chars=1800,
        )
        return parser.get_nodes_from_documents(documents)

    parser = SentenceSplitter(chunk_size=1200, chunk_overlap=100)
    return parser.get_nodes_from_documents(documents)


def _contains_table(text: str) -> bool:
    stripped = text.strip()
    return "<table" in stripped or ("|" in stripped and "---" in stripped)


def recursive_split_nodes(nodes: List[Any], options: PipelineOptions) -> List[Any]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=options.recursive_chunk_size,
        chunk_overlap=options.recursive_chunk_overlap,
        separators=["\n\n", "\n", "。", "；", "，", " ", ""],
    )
    try:
        parser = LangchainNodeParser(lc_splitter=text_splitter)
    except TypeError:
        parser = LangchainNodeParser(text_splitter=text_splitter)

    recursive_docs: List[Document] = []
    for node in nodes:
        text = node.get_content()
        if not text or not text.strip():
            continue
        recursive_docs.append(Document(text=text, metadata=getattr(node, "metadata", {}) or {}))

    non_table_docs = [doc for doc in recursive_docs if not _contains_table(doc.text)]
    table_docs = [doc for doc in recursive_docs if _contains_table(doc.text)]

    split_nodes: List[Any] = []
    if non_table_docs:
        split_nodes.extend(parser.get_nodes_from_documents(non_table_docs))
    split_nodes.extend(table_docs)
    return split_nodes


def semantic_refine_nodes(nodes: List[Any], options: PipelineOptions) -> List[Any]:
    embed_model = get_embed_model()
    if embed_model is None:
        return nodes

    semantic_docs: List[Document] = []
    preserved_nodes: List[Any] = []
    for node in nodes:
        text = node.get_content()
        if not text or not text.strip():
            continue
        if _contains_table(text):
            preserved_nodes.append(node)
            continue
        semantic_docs.append(Document(text=text, metadata=getattr(node, "metadata", {}) or {}))

    if not semantic_docs:
        return preserved_nodes

    parser = SemanticSplitterNodeParser(
        embed_model=embed_model,
        buffer_size=options.semantic_buffer_size,
        breakpoint_percentile_threshold=options.semantic_breakpoint_percentile_threshold,
    )
    return parser.get_nodes_from_documents(semantic_docs) + preserved_nodes


def _extract_markdown_headings(text: str) -> List[tuple[int, str]]:
    headings: List[tuple[int, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("#"):
            continue
        level = len(line) - len(line.lstrip("#"))
        title = line[level:].strip()
        if title:
            headings.append((level, title))
    return headings


def _normalize_header_path(header_path: Any) -> List[str]:
    if not isinstance(header_path, str):
        return []
    return [part.strip() for part in header_path.split("/") if part.strip() and part.strip() != "/"]


def enrich_chunks_with_title_path(chunks: List[Dict[str, Any]], source_file: str) -> List[Dict[str, Any]]:
    heading_stack: List[str] = []
    enriched_chunks: List[Dict[str, Any]] = []

    for chunk in chunks:
        text = chunk.get("text", "")
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

        metadata["title_path"] = title_path
        enriched_chunks.append(
            {
                "text": text,
                "metadata": metadata,
                "title_path": title_path,
                "retrieval_text": retrieval_text,
            }
        )

    return enriched_chunks


def split_document_sync(file_path: Path, options: PipelineOptions) -> List[Dict[str, Any]]:
    reader = SimpleDirectoryReader(input_files=[str(file_path)], required_exts=[file_path.suffix])
    docs = reader.load_data()
    if not docs:
        return []

    format_nodes = parse_by_format(file_path, docs)
    recursive_nodes = recursive_split_nodes(format_nodes, options)

    try:
        semantic_nodes = semantic_refine_nodes(recursive_nodes, options)
    except Exception as exc:
        print(f"[警告] 语义切分失败，回退到递归切分结果: {exc}")
        semantic_nodes = recursive_nodes

    chunks: List[Dict[str, Any]] = []
    for node in semantic_nodes:
        text = node.get_content()
        if not text or not text.strip():
            continue
        chunks.append({"text": text, "metadata": getattr(node, "metadata", {}) or {}})
    return enrich_chunks_with_title_path(chunks, file_path.name)


async def split_document_async(file_path: Path, options: PipelineOptions) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(split_document_sync, file_path, options)


def append_chunk(chunk_file: Path, data: Dict[str, Any]) -> None:
    chunk_file.parent.mkdir(parents=True, exist_ok=True)
    with chunk_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def count_existing_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f)


async def process_one_document(
    file_path: Path,
    input_dir: Path,
    output_dir: Path,
    checkpoint_file: Path,
    options: PipelineOptions,
) -> str:
    rel_path = safe_rel_path(file_path, input_dir)
    safe_name = sanitize_rel_for_output(rel_path)
    chunk_file = output_dir / f"{safe_name}.chunks.jsonl"

    async with CHECKPOINT_LOCK:
        checkpoint_data = load_checkpoint(checkpoint_file)
        docs_state = checkpoint_data.setdefault("documents", {})
        entry = docs_state.get(rel_path, {})

        if entry.get("status") == "completed" and chunk_file.exists():
            print(f"[跳过] 已完成: {rel_path}")
            return "done"

        entry.setdefault("source_path", rel_path)
        entry.setdefault("chunks_file", str(chunk_file))
        entry.setdefault("status", "pending")
        entry.setdefault("next_chunk_index", 0)

        if entry["next_chunk_index"] > 0 and not chunk_file.exists():
            print(f"[警告] 检测到断点但 chunks 文件丢失，重置断点: {rel_path}")
            entry["next_chunk_index"] = 0

        real_count = count_existing_lines(chunk_file)
        if real_count != entry["next_chunk_index"]:
            entry["next_chunk_index"] = real_count

        docs_state[rel_path] = entry
        save_checkpoint(checkpoint_file, checkpoint_data)

    print(f"[处理] {rel_path}")
    if entry["next_chunk_index"] > 0:
        print(f"[恢复] 从 chunk #{entry['next_chunk_index']} 继续")

    try:
        chunks = await split_document_async(file_path, options)
    except Exception as exc:
        async with CHECKPOINT_LOCK:
            checkpoint_data = load_checkpoint(checkpoint_file)
            docs_state = checkpoint_data.setdefault("documents", {})
            fail_entry = docs_state.get(rel_path, {})
            fail_entry["source_path"] = rel_path
            fail_entry["chunks_file"] = str(chunk_file)
            fail_entry["status"] = "failed"
            fail_entry["error"] = str(exc)
            fail_entry["updated_at"] = now_str()
            docs_state[rel_path] = fail_entry
            save_checkpoint(checkpoint_file, checkpoint_data)
        print(f"[失败] {rel_path}: {exc}")
        return "failed"

    start_index = int(entry.get("next_chunk_index", 0))
    total = len(chunks)
    if start_index > total:
        start_index = total

    for idx in range(start_index, total):
        chunk_payload = {
            "source_file": rel_path,
            "chunk_index": idx,
            "text": chunks[idx]["text"],
            "title_path": chunks[idx].get("title_path", ""),
            "retrieval_text": chunks[idx].get("retrieval_text", chunks[idx]["text"]),
            "metadata": chunks[idx].get("metadata", {}),
        }
        append_chunk(chunk_file, chunk_payload)

        async with CHECKPOINT_LOCK:
            checkpoint_data = load_checkpoint(checkpoint_file)
            docs_state = checkpoint_data.setdefault("documents", {})
            progress_entry = docs_state.get(rel_path, {})
            progress_entry["source_path"] = rel_path
            progress_entry["chunks_file"] = str(chunk_file)
            progress_entry["status"] = "processing"
            progress_entry["next_chunk_index"] = idx + 1
            progress_entry["updated_at"] = now_str()
            docs_state[rel_path] = progress_entry
            save_checkpoint(checkpoint_file, checkpoint_data)

        print(f"  [断点] 已写入 chunk {idx + 1}/{total}")

    async with CHECKPOINT_LOCK:
        checkpoint_data = load_checkpoint(checkpoint_file)
        docs_state = checkpoint_data.setdefault("documents", {})
        done_entry = docs_state.get(rel_path, {})
        done_entry["source_path"] = rel_path
        done_entry["chunks_file"] = str(chunk_file)
        done_entry["status"] = "completed"
        done_entry["total_chunks"] = total
        done_entry["next_chunk_index"] = total
        done_entry["updated_at"] = now_str()
        docs_state[rel_path] = done_entry
        save_checkpoint(checkpoint_file, checkpoint_data)

    print(f"[完成] {rel_path} -> {chunk_file}")
    return "done"


async def node_discover_files(state: ChunkGraphState) -> Dict[str, Any]:
    input_dir = Path(state["input_dir"])
    files = collect_input_files(input_dir)
    print(f"[节点] 发现文档: {len(files)} 个")
    return {"all_files": [str(p) for p in files]}


async def node_process_single_file(state: FileGraphState) -> Dict[str, Any]:
    file_path = Path(state["file_path"])
    if not file_path.exists():
        return {"result": "skipped"}

    result = await process_one_document(
        file_path=file_path,
        input_dir=Path(state["input_dir"]),
        output_dir=Path(state["output_dir"]),
        checkpoint_file=Path(state["checkpoint_file"]),
        options=PipelineOptions(),
    )
    return {"result": result}


async def partition_files(
    files: list[Path],
    input_dir: Path,
    output_dir: Path,
    checkpoint_file: Path,
    options: PipelineOptions | None = None,
) -> Dict[str, int]:
    options = options or PipelineOptions()
    output_dir.mkdir(parents=True, exist_ok=True)

    done = 0
    failed = 0
    total_chunks = 0
    for file_path in files:
        result = await process_one_document(
            file_path=file_path,
            input_dir=input_dir,
            output_dir=output_dir,
            checkpoint_file=checkpoint_file,
            options=options,
        )
        if result == "done":
            done += 1
            rel_path = safe_rel_path(file_path, input_dir)
            safe_name = sanitize_rel_for_output(rel_path)
            chunk_file = output_dir / f"{safe_name}.chunks.jsonl"
            total_chunks += count_existing_lines(chunk_file)
        elif result == "failed":
            failed += 1

    return {"done": done, "failed": failed, "chunks": total_chunks}


def build_file_subgraph() -> Any:
    builder = StateGraph(FileGraphState)
    builder.add_node("process_single_file", node_process_single_file)
    builder.set_entry_point("process_single_file")
    builder.add_edge("process_single_file", END)
    return builder.compile()


async def run_file_subgraph(
    file_path: str,
    input_dir: str,
    output_dir: str,
    checkpoint_file: str,
) -> str:
    subgraph = build_file_subgraph()
    result = await subgraph.ainvoke(
        {
            "file_path": file_path,
            "input_dir": input_dir,
            "output_dir": output_dir,
            "checkpoint_file": checkpoint_file,
            "result": "",
        }
    )
    return result.get("result", "failed")


async def node_run_subgraphs(state: ChunkGraphState) -> Dict[str, Any]:
    input_dir = Path(state["input_dir"])
    output_dir = Path(state["output_dir"])
    checkpoint_file = Path(state["checkpoint_file"])
    output_dir.mkdir(parents=True, exist_ok=True)

    done_files: List[str] = []
    failed_files: List[str] = []
    skipped_files: List[str] = []

    file_paths = state.get("all_files", [])
    coroutines = [
        run_file_subgraph(
            file_path=file_path,
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            checkpoint_file=str(checkpoint_file),
        )
        for file_path in file_paths
    ]

    results = await asyncio.gather(*coroutines, return_exceptions=True)
    for file_path, result in zip(file_paths, results):
        if isinstance(result, Exception):
            failed_files.append(file_path)
            print(f"[失败] 子图执行异常: {file_path}: {result}")
            continue

        if result == "done":
            done_files.append(file_path)
        elif result == "failed":
            failed_files.append(file_path)
        else:
            skipped_files.append(file_path)

    return {"done_files": done_files, "failed_files": failed_files, "skipped_files": skipped_files}


def node_summary(state: ChunkGraphState) -> Dict[str, Any]:
    total = len(state.get("all_files", []))
    done = len(state.get("done_files", []))
    failed = len(state.get("failed_files", []))
    skipped = len(state.get("skipped_files", []))

    print("\n" + "=" * 56)
    print("[汇总] LangGraph 文档切分完成")
    print("=" * 56)
    print(f"总数: {total}")
    print(f"成功: {done}")
    print(f"失败: {failed}")
    print(f"跳过: {skipped}")

    if failed:
        print("\n失败文件:")
        for path in state["failed_files"]:
            print(f"  - {path}")

    return {}


def build_graph() -> Any:
    graph_builder = StateGraph(ChunkGraphState)
    graph_builder.add_node("discover_files", node_discover_files)
    graph_builder.add_node("run_subgraphs", node_run_subgraphs)
    graph_builder.add_node("summary", node_summary)

    graph_builder.set_entry_point("discover_files")
    graph_builder.add_edge("discover_files", "run_subgraphs")
    graph_builder.add_edge("run_subgraphs", "summary")
    graph_builder.add_edge("summary", END)

    return graph_builder.compile()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LangGraph 异步文档切分工具（支持断点恢复）")
    parser.add_argument("--input-file", type=str, default=None, help="仅切分单个文件")
    parser.add_argument("--input-dir", type=str, default=None, help="输入目录（覆盖默认 rag 路径）")
    parser.add_argument("--output-dir", type=str, default=None, help="输出目录（覆盖默认 rag 路径）")
    parser.add_argument("--checkpoint-file", type=str, default=None, help="checkpoint 文件路径")
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
    checkpoint_file = Path(args.checkpoint_file) if args.checkpoint_file else output_dir / ".partition_checkpoint.json"

    print("LangGraph 异步文档切分工具")
    print(f"输入目录: {input_dir}")
    print(f"输出目录: {output_dir}")
    print(f"断点文件: {checkpoint_file}")

    if args.input_file:
        result = await partition_files(
            files=[Path(args.input_file)],
            input_dir=input_dir,
            output_dir=output_dir,
            checkpoint_file=checkpoint_file,
            options=options,
        )
        print(f"[汇总] done={result['done']} failed={result['failed']} chunks={result['chunks']}")
        return

    graph = build_graph()
    initial_state: ChunkGraphState = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "checkpoint_file": str(checkpoint_file),
        "all_files": [],
        "done_files": [],
        "failed_files": [],
        "skipped_files": [],
    }

    await graph.ainvoke(initial_state)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
