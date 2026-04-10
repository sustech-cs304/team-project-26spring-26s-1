"""Embedding 与向量存储工具。

该模块负责：
1. 从切分结果 JSONL 读取 chunk；
2. 生成 embedding；
3. 将结果写入 LangGraph SQLite store；
4. 为检索工具提供 indexed store 构建能力。
"""

import asyncio
import json
from pathlib import Path

from langchain.tools import ToolRuntime, tool
from langchain_openai import OpenAIEmbeddings
from langgraph.store.sqlite import AsyncSqliteStore

NAMESPACE = "embeddings"


def _infer_document_type(chunk: dict) -> str:
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    document_type = str(metadata.get("document_type") or "").strip()
    if document_type:
        return document_type

    source_file = str(chunk.get("source_file") or metadata.get("file_name") or "")
    title_path = str(chunk.get("title_path") or metadata.get("title_path") or "")
    text = str(chunk.get("text") or "")
    combined = f"{source_file}\n{title_path}\n{text}"
    if "学生手册" in combined:
        return "学生手册"
    return "培养方案"


def _infer_handbook_section(chunk: dict) -> str:
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    if str(metadata.get("document_type") or _infer_document_type(chunk)) != "学生手册":
        return ""

    title_path = str(chunk.get("title_path") or metadata.get("title_path") or "")
    if title_path:
        return title_path
    text = str(chunk.get("text") or "").strip().splitlines()
    return text[0].lstrip("# ").strip() if text else ""


def _normalize_chunk(chunk: dict) -> dict:
    normalized = dict(chunk)
    metadata = normalized.get("metadata")
    metadata = dict(metadata) if isinstance(metadata, dict) else {}

    document_type = _infer_document_type(normalized)
    metadata.setdefault("document_type", document_type)
    metadata.setdefault("title_path", normalized.get("title_path", ""))

    if document_type == "学生手册":
        metadata.setdefault("handbook_section", _infer_handbook_section(normalized))
        metadata.setdefault("policy_topic", metadata.get("handbook_section", ""))

    normalized["metadata"] = metadata
    return normalized


async def embed_texts(
    texts: list[str], 
    embedding_config
) -> list[list[float]]:
    """
    使用 embedding_model 对文本进行嵌入。
    
    Args:
        texts: 待嵌入的文本列表
        embedding_config: 来自 config.yaml 的嵌入配置
        
    Returns:
        嵌入向量列表
    """
    embeddings = OpenAIEmbeddings(
        model=embedding_config.model,
        api_key=embedding_config.api_key,
        base_url=embedding_config.base_url,
    )
    
    # 使用线程池异步嵌入文本
    embedded = await asyncio.gather(
        *[asyncio.to_thread(embeddings.embed_query, text) for text in texts]
    )
    
    return embedded


def build_indexed_store(runtime_store, embedding_config) -> AsyncSqliteStore:
    """Create an indexed SQLite store wrapper on top of the existing connection."""
    if not hasattr(runtime_store, "conn"):
        raise ValueError("Runtime store does not expose a SQLite connection.")

    embeddings = OpenAIEmbeddings(
        model=embedding_config.model,
        api_key=embedding_config.api_key,
        base_url=embedding_config.base_url,
    )
    return AsyncSqliteStore(
        runtime_store.conn,
        index={
            "dims": embedding_config.dims,
            "embed": embeddings,
            "fields": ["retrieval_text"],
            "distance_type": "cosine",
        },
    )


async def load_chunks_from_jsonl(directory_path: str) -> list[dict]:
    """
    从指定目录读取所有 .jsonl 文件中的 chunks。
    
    Args:
        directory_path: 包含 .jsonl 文件的目录路径
        
    Returns:
        chunks 列表，每个 chunk 包含 source_file, chunk_index, text, metadata
    """
    chunks = []
    directory = Path(directory_path)
    
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")
    
    jsonl_files = list(directory.glob("*.jsonl"))
    
    for jsonl_file in jsonl_files:
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    chunk = json.loads(line)
                    chunks.append(_normalize_chunk(chunk))
    
    return chunks


async def store_embeddings(
    runtime: ToolRuntime, 
    chunks: list[dict]
) -> None:
    """
    对 chunks 进行嵌入并存储到 store 中。
    
    Args:
        runtime: ToolRuntime 对象，包含 store 引用
        chunks: 待处理的 chunks 列表
        
    Raises:
        ValueError: 如果 store 不可用
        Exception: 如果嵌入或存储过程中出错
    """
    store = runtime.store
    if not store:
        raise ValueError("Store is not available from runtime")
    
    # config = load_config()
    config = runtime.config
    embedding_config = config.api.embed

    indexed_store = build_indexed_store(store, embedding_config)
    await indexed_store.setup()

    texts = [chunk["text"] for chunk in chunks]
    embeddings = await embed_texts(texts, embedding_config)

    for chunk, embedding in zip(chunks, embeddings):
        source_file = chunk.get("source_file", "unknown")
        chunk_index = chunk.get("chunk_index", 0)
        metadata = chunk.get("metadata", {}) if isinstance(chunk.get("metadata"), dict) else {}
        
        key = f"{source_file}#{chunk_index}"
        
        value = {
            "text": chunk.get("text", ""),
            "title_path": chunk.get("title_path", ""),
            "retrieval_text": chunk.get("retrieval_text")
            or "\n".join(
                [
                    source_file,
                    chunk.get("title_path", ""),
                    chunk.get("text", ""),
                ]
            ),
            "source_file": source_file,
            "chunk_index": chunk_index,
            "metadata": metadata,
            "embedding": embedding,
        }
        
        await indexed_store.aput((NAMESPACE,), key=key, value=value, index=["retrieval_text"])


async def embed_and_store_chunks(runtime: ToolRuntime) -> str:
    """Embed and store partitioned chunks into the unified RAG database.

    This tool is intended for ingestion after document cleaning and chunking.
    It supports a shared single-database setup for both program documents and
    student handbook documents.

    Current behavior:
    - reads `.jsonl` chunk files from `output_partitioned`
    - normalizes metadata such as `document_type` for unified storage
    - generates embeddings from the runtime embedding configuration
    - stores `text`, `title_path`, `retrieval_text`, `metadata`, and `embedding`
      into the vector-enabled store

    Recommended usage:
    - use this during data ingestion or rebuild workflows
    - run it after new partition outputs are produced
    - use it before retrieval validation if the database was updated

    Returns:
        A success message with the processed chunk count, or an `Error:` message.
    """
    try:
        # 从 output_partitioned 目录读取 chunks
        chunks = await load_chunks_from_jsonl("output_partitioned")
        
        if not chunks:
            return "No chunks found in output_partitioned directory."
        
        # 嵌入并存储 chunks
        await store_embeddings(runtime, chunks)
        
        return f"Successfully processed {len(chunks)} chunks."
        
    except FileNotFoundError as e:
        return f"Error: {str(e)}"
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error: Failed to embed and store chunks: {str(e)}"
