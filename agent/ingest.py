"""
agent-ingest  —  CLI tool for inserting plain-text documents into the RAG knowledge base.

Usage
-----
    agent-ingest path/to/document.txt
    agent-ingest path/to/document.txt --source "Product Manual v2"
    agent-ingest path/to/document.txt --chunk-size 150 --chunk-overlap 2 --batch-size 64

The file is split into sentence fragments (on sentence-ending punctuation) and
reassembled into chunks whose word count does not exceed --chunk-size. Consecutive
chunks overlap by --chunk-overlap *sentences* so that context is not lost at
boundaries. Chunks are then embedded in batches and upserted into the local qdrant
RAG collection.
Existing entries for the same source label are NOT removed automatically; re-ingesting
the same file will add duplicate entries. Use `agent-ingest --clear-source` (future) or
manually delete via qdrant tooling if a refresh is needed.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import uuid
from pathlib import Path

from openai import AsyncOpenAI

from qdrant_client import AsyncQdrantClient

from .config import Config
from .vectorstore import VectorStore


# ---------------------------------------------------------------------------
# Text processing
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> list[str]:
    """Split *text* into sentence fragments on sentence-ending punctuation.

    Two split rules are combined:

    1. ASCII terminals (. ! ?) — requires trailing whitespace or end-of-string
       to avoid splitting on abbreviations like "Dr." or version numbers like "3.14".

    2. CJK terminals (。！？…) — splits immediately after the character with no
       whitespace requirement, since CJK prose does not use spaces between sentences.
       The ellipsis 「…」 (U+2026) is included because it commonly ends a CJK
       utterance even though it is not strictly a full stop.

    Each returned fragment is stripped and non-empty.
    """
    # Rule 1: ASCII .  !  ?  followed by whitespace or end-of-string
    # Rule 2: CJK  。 ！ ？ …  followed by anything (no whitespace required)
    parts = re.split(r'(?<=[.!?])(?=\s|$)|(?<=[。！？…])', text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split *text* into overlapping chunks reassembled from sentence fragments.

    Sentence fragments are accumulated until adding the next fragment would
    exceed *chunk_size* words, at which point the current chunk is saved and a
    new one starts with *chunk_overlap* trailing sentences carried over so that
    context across boundaries is preserved.

    Long single sentences that exceed *chunk_size* on their own are included as
    their own chunk rather than silently dropped.

    Args:
        text:          Raw document text.
        chunk_size:    Maximum words per chunk.
        chunk_overlap: Number of trailing sentences to carry into the next chunk.

    Returns:
        List of non-empty chunk strings.
    """
    sentences = _split_sentences(text)
    print(f"Split into {len(sentences)} sentences.")
    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []   # sentences in the current chunk
    current_words = 0

    for sentence in sentences:
        s_words = len(sentence)

        if current_words + s_words > chunk_size and current:
            # Save the current chunk
            chunks.append(" ".join(current))
            # Carry over the last `chunk_overlap` sentences into the next chunk
            overlap = current[-chunk_overlap:] if chunk_overlap > 0 else []
            current = list(overlap)
            current_words = sum(len(s.split()) for s in current)

        current.append(sentence)
        current_words += s_words

    if current:
        chunks.append(" ".join(current))

    return chunks


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

async def ingest_file(
    filepath: Path,
    config: Config | None = None,
    source: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    batch_size: int | None = None,
) -> None:
    """Read a plain-text file, chunk, embed in batches, and upsert into the RAG KB.

    Args:
        filepath:      Path to the .txt file.
        config:        Agent configuration (defaults loaded from YAML if omitted).
        source:        Human-readable label stored alongside each chunk as metadata.
                       Defaults to the filename if not provided.
        chunk_size:    Words per chunk.
        chunk_overlap: Word overlap between consecutive chunks.
        batch_size:    Texts per embedding API call.
    """
    if config is None:
        config = Config.from_yaml()

    if chunk_size is None:
        chunk_size = config.rag_chunk_size
    if chunk_overlap is None:
        chunk_overlap = config.rag_chunk_overlap
    if batch_size is None:
        batch_size = config.rag_embed_batch_size

    if not filepath.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    if not filepath.is_file():
        print(f"Error: path is not a file: {filepath}", file=sys.stderr)
        sys.exit(1)

    source_label = source or filepath.name
    print(f"Reading   {filepath}")
    print(f"Source    '{source_label}'")

    text = filepath.read_text(encoding="utf-8", errors="replace")
    print(f"File size {len(text)} characters")
    chunks = chunk_text(text, chunk_size, chunk_overlap)
    if not chunks:
        print("File produced no chunks — is it empty?", file=sys.stderr)
        sys.exit(1)

    print(
        f"Chunked   {len(chunks)} segments  "
        f"(chunk_size={chunk_size} words, overlap={chunk_overlap} sentences)"
    )

    embed_client = AsyncOpenAI(base_url=config.embed_api_base_url, api_key=config.embed_api_key)
    config.agent_qdrant_path.mkdir(parents=True, exist_ok=True)
    qdrant = AsyncQdrantClient(path=str(config.agent_qdrant_path))
    try:
        store = VectorStore(
            client=embed_client,
            qdrant=qdrant,
            collection=config.rag_collection_name,
            embed_model=config.embed_model,
            embed_dims=config.embed_dims,
        )

        print(f"Embedding via {config.embed_model} …")
        vectors = await store.embed_batched(chunks, batch_size=batch_size, progress=True)

        records = [
            {
                "id": str(uuid.uuid4()),
                "vector": vec,
                "payload": {"text": chunk, "source": source_label, "chunk_index": idx},
            }
            for idx, (chunk, vec) in enumerate(zip(chunks, vectors))
        ]

        print(f"Upserting {len(records)} points into '{config.rag_collection_name}' …")
        await store.upsert_records(records, batch_size=batch_size, progress=True)
    finally:
        await qdrant.close()

    print(f"Done. Inserted {len(records)} chunks from '{source_label}'.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    config = Config.from_yaml()

    parser = argparse.ArgumentParser(
        prog="agent-ingest",
        description="Insert a plain-text file into the agent's RAG knowledge base.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to the plain-text (.txt) file to ingest.",
    )
    parser.add_argument(
        "--source",
        default=None,
        metavar="LABEL",
        help="Human-readable label for this document (default: filename).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=config.rag_chunk_size,
        metavar="N",
        help=f"Words per chunk (default: {config.rag_chunk_size}).",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=config.rag_chunk_overlap,
        metavar="N",
        help=f"Sentences of overlap carried into the next chunk (default: {config.rag_chunk_overlap}).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=config.rag_embed_batch_size,
        metavar="N",
        help=f"Texts per embedding API call (default: {config.rag_embed_batch_size}).",
    )

    args = parser.parse_args()
    asyncio.run(ingest_file(
        filepath=args.file,
        config=config,
        source=args.source,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        batch_size=args.batch_size,
    ))


if __name__ == "__main__":
    main()
