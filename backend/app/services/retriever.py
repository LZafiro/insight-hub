"""Hybrid retrieval combining dense (pgvector) and sparse (BM25/FTS) search."""

import asyncio
from uuid import UUID

from app.domain.models import Chunk
from app.repositories.chunks import ChunkRepository
from app.services.embeddings import EmbeddingProvider


class HybridRetriever:
    _RRF_K = 60

    def __init__(self, chunk_repo: ChunkRepository, embeddings: EmbeddingProvider) -> None:
        self._chunks = chunk_repo
        self._embeddings = embeddings

    async def retrieve(self, query: str, workspace_id: UUID, candidate_k: int = 20) -> list[Chunk]:
        query_vec = await self._embeddings.embed_one(query)
        dense_results, bm25_results = await asyncio.gather(
            self._chunks.search_dense(query_vec, workspace_id, top_n=candidate_k),
            self._chunks.search_bm25(query, workspace_id, top_n=candidate_k),
        )
        return self._rrf_fuse(dense_results, bm25_results, top_k=candidate_k)

    @classmethod
    def _rrf_fuse(
        cls,
        dense: list[tuple[Chunk, float]],
        bm25: list[tuple[Chunk, float]],
        top_k: int,
    ) -> list[Chunk]:
        scores: dict[UUID, float] = {}
        index: dict[UUID, Chunk] = {}

        for rank, (chunk, _) in enumerate(dense):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (cls._RRF_K + rank + 1)
            index[chunk.id] = chunk

        for rank, (chunk, _) in enumerate(bm25):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (cls._RRF_K + rank + 1)
            index[chunk.id] = chunk

        ranked = sorted(scores, key=lambda cid: scores[cid], reverse=True)
        return [index[cid] for cid in ranked[:top_k]]
