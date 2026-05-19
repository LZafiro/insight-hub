"""Cross-encoder re-ranking."""

import asyncio
from typing import Protocol

from app.domain.models import Chunk


class RerankProvider(Protocol):
    async def rerank(self, query: str, chunks: list[Chunk], top_k: int) -> list[Chunk]: ...


class CrossEncoderReranker:
    _MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self) -> None:
        self._model = None

    def _load(self) -> object:
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self._MODEL_NAME)
        return self._model

    async def rerank(self, query: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
        if not chunks:
            return []
        pairs = [(query, chunk.content) for chunk in chunks]
        model = self._load()
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(None, model.predict, pairs)
        ranked = sorted(zip(chunks, scores), key=lambda x: float(x[1]), reverse=True)
        return [chunk for chunk, _ in ranked[:top_k]]
