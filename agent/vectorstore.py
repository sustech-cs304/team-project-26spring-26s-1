"""
Shared Qdrant vector store and embedding utilities.

A VectorStore instance owns exactly one QdrantClient (one RocksDB file lock)
and one named collection within it.  This is the primitive building block for
any semantic-search capability in the agent: RAG knowledge base, skills store,
etc.

IMPORTANT — one path, one owner:
    Local Qdrant uses RocksDB, which places an exclusive file lock on the
    database directory. Never create two VectorStore (or any other
    QdrantClient) instances pointing at the same path inside the same process.
    Use separate DATA_DIR sub-paths for each independent store, or switch to
    Qdrant server mode (QdrantClient(host=..., port=...)) which multiplexes
    all clients safely.
"""

from __future__ import annotations

import uuid

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


class VectorStore:
    """Thin wrapper around a local Qdrant collection with OpenAI embeddings.

    Handles client lifecycle, collection creation, embedding, search, and
    batched upsert so that higher-level modules (rag.py, skills.py, …)
    contain zero Qdrant boilerplate.
    """

    def __init__(
        self,
        client: AsyncOpenAI,
        qdrant: AsyncQdrantClient,
        collection: str,
        embed_model: str,
        embed_dims: int,
    ) -> None:
        self._client = client
        self._qdrant = qdrant
        self._collection = collection
        self._embed_model = embed_model
        self._embed_dims = embed_dims
        self._collection_ready = False

    # ------------------------------------------------------------------
    # Lifecycle — the QdrantClient is caller-owned; VectorStore does not
    # close it. The caller is responsible for close() and atexit.
    # ------------------------------------------------------------------

    async def _ensure_collection(self) -> None:
        if self._collection_ready:
            return
        existing = {c.name for c in (await self._qdrant.get_collections()).collections}
        if self._collection not in existing:
            await self._qdrant.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=self._embed_dims, distance=Distance.COSINE),
            )
        self._collection_ready = True

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed *texts* in a single API call.

        For large text lists use embed_batched to avoid hitting per-request
        token/item limits.
        """
        response = await self._client.embeddings.create(model=self._embed_model, input=texts)
        return [r.embedding for r in response.data]

    async def embed_batched(
        self,
        texts: list[str],
        batch_size: int,
        progress: bool = False,
    ) -> list[list[float]]:
        """Embed *texts* in chunks of *batch_size*, optionally printing progress.

        Vectors are returned in the same order as *texts*.
        """
        embeddings: list[list[float]] = []
        total = len(texts)
        for i in range(0, total, batch_size):
            batch = texts[i : i + batch_size]
            response = await self._client.embeddings.create(model=self._embed_model, input=batch)
            embeddings.extend(r.embedding for r in response.data)
            if progress:
                done = min(i + batch_size, total)
                print(f"  Embedded {done}/{total} chunks …", end="\r", flush=True)
        if progress:
            print()
        return embeddings

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(self, query: str, top_k: int) -> list[dict]:
        """Return the *top_k* most similar points for *query*.

        Each result is a dict: ``{"score": float, "payload": dict}``.
        The caller is responsible for interpreting payload fields.
        """
        await self._ensure_collection()
        vec = (await self.embed([query]))[0]
        hits = (await self._qdrant.query_points(
            collection_name=self._collection,
            query=vec,
            limit=top_k,
        )).points
        return [
            {"score": round(hit.score, 4), "payload": hit.payload}
            for hit in hits
        ]

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def delete_by_id(self, point_id: str) -> None:
        """Delete a single point by its ID.  Silently succeeds if the ID does not exist."""
        await self._ensure_collection()
        await self._qdrant.delete(
            collection_name=self._collection,
            points_selector=[point_id],
        )

    async def clear_collection(self) -> None:
        """Delete and recreate the collection, removing all stored vectors."""
        await self._qdrant.delete_collection(collection_name=self._collection)
        self._collection_ready = False
        await self._ensure_collection()

    async def upsert_records(
        self,
        records: list[dict],
        batch_size: int,
        progress: bool = False,
    ) -> None:
        """Upsert a list of record dicts into the collection in batches.

        Each record must have:
            ``id``      – str (UUID or any unique string)
            ``vector``  – list[float]
            ``payload`` – dict of arbitrary metadata

        If ``id`` is omitted a random UUID is generated automatically.
        """
        points = [
            PointStruct(
                id=r.get("id", str(uuid.uuid4())),
                vector=r["vector"],
                payload=r["payload"],
            )
            for r in records
        ]
        await self._ensure_collection()
        total = len(points)
        for i in range(0, total, batch_size):
            await self._qdrant.upsert(
                collection_name=self._collection,
                points=points[i : i + batch_size],
            )
            if progress:
                done = min(i + batch_size, total)
                print(f"  Upserted {done}/{total} points …", end="\r", flush=True)
        if progress:
            print()
