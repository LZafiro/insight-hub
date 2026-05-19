"""Embedding generation."""

from typing import Protocol

from openai import AsyncOpenAI

from app.core.config import settings


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_one(self, text: str) -> list[float]: ...


class OpenAIEmbeddings:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # OpenAI accepts a batch in one call — much cheaper than serial calls.
        resp = await self._client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in resp.data]

    async def embed_one(self, text: str) -> list[float]:
        result = await self.embed([text])
        return result[0]


def build_embedding_provider() -> EmbeddingProvider:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY required for embeddings")
    return OpenAIEmbeddings(api_key=settings.openai_api_key, model=settings.embedding_model)
