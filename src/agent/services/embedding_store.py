import asyncio
import json
from pathlib import Path

from langchain.tools import ToolRuntime
from langchain_openai import OpenAIEmbeddings
from langgraph.store.sqlite import AsyncSqliteStore

from agent.config import get_config, get_config_path, require_embedding_config

NAMESPACE = "embeddings"


async def embed_texts(
    texts: list[str],
    embedding_config,
) -> list[list[float]]:
    """
    使用 embedding_model 对文本进行嵌入。

    Args:
        texts: 待嵌入的文本列表
        embedding_config: 来自 config.yaml 的嵌入配置

    Returns:
        嵌入向量列表
    """
    embedding_config = require_embedding_config(embedding_config)
    embeddings = OpenAIEmbeddings(
        model=embedding_config.model,
        api_key=embedding_config.api_key,
        base_url=embedding_config.base_url,
    )

    embedded = await asyncio.gather(
        *[asyncio.to_thread(embeddings.embed_query, text) for text in texts]
    )

    return embedded


def build_indexed_store(runtime_store, embedding_config) -> AsyncSqliteStore:
    """Create an indexed SQLite store wrapper on top of the existing connection."""
    if not hasattr(runtime_store, "conn"):
        raise ValueError("Runtime store does not expose a SQLite connection.")

    embedding_config = require_embedding_config(embedding_config)
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
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunk = json.loads(line)
                    chunks.append(chunk)

    return chunks


async def store_embeddings(
    runtime: ToolRuntime,
    chunks: list[dict],
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

    embedding_config = require_embedding_config(get_config_path(get_config(), "api.embed"))

    indexed_store = build_indexed_store(store, embedding_config)
    await indexed_store.setup()

    texts = [chunk["text"] for chunk in chunks]
    embeddings = await embed_texts(texts, embedding_config)

    for chunk, embedding in zip(chunks, embeddings):
        source_file = chunk.get("source_file", "unknown")
        chunk_index = chunk.get("chunk_index", 0)

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
            "metadata": chunk.get("metadata", {}),
            "embedding": embedding,
        }

        await indexed_store.aput(
            (NAMESPACE,),
            key=key,
            value=value,
            index=["retrieval_text"],
        )
