"""Document ingestion: parse → chunk → embed → persist."""

import io
from dataclasses import dataclass
from uuid import UUID

import tiktoken
from pypdf import PdfReader

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.models import Chunk, Document, DocumentStatus
from app.repositories.chunks import ChunkRepository
from app.services.embeddings import EmbeddingProvider

log = get_logger(__name__)


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    page_count: int


class UnsupportedContentTypeError(ValueError):
    """Raised for content types the ingestion pipeline can't parse."""


class IngestionService:
    def __init__(self, chunk_repo: ChunkRepository, embeddings: EmbeddingProvider) -> None:
        self._chunks = chunk_repo
        self._embeddings = embeddings
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    async def ingest(self, document: Document, raw: bytes) -> int:
        """Parse, chunk, embed, persist. Returns the number of chunks created."""
        try:
            parsed = self._parse(raw, content_type=document.content_type)
            texts = self._chunk(parsed.text)
            log.info("ingestion.chunked", document_id=str(document.id), chunks=len(texts))

            embeddings = await self._embeddings.embed(texts)

            chunks = [
                Chunk(
                    document_id=document.id,
                    workspace_id=document.workspace_id,
                    ordinal=i,
                    content=text,
                    embedding=vec,
                    token_count=len(self._tokenizer.encode(text)),
                )
                for i, (text, vec) in enumerate(zip(texts, embeddings, strict=True))
            ]
            await self._chunks.bulk_insert(chunks)

            document.status = DocumentStatus.READY
            document.doc_metadata = {"page_count": parsed.page_count, "chunk_count": len(chunks)}
            return len(chunks)
        except Exception as e:
            log.exception("ingestion.failed", document_id=str(document.id), error=str(e))
            document.status = DocumentStatus.FAILED
            document.error_message = str(e)[:500]
            raise

    # ---- internals ----

    def _parse(self, raw: bytes, content_type: str) -> ParsedDocument:
        if content_type == "application/pdf":
            reader = PdfReader(io.BytesIO(raw))
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
            return ParsedDocument(text=text, page_count=len(reader.pages))
        if content_type.startswith("text/"):
            return ParsedDocument(text=raw.decode("utf-8", errors="replace"), page_count=1)
        raise UnsupportedContentTypeError(f"Cannot parse content type: {content_type}")

    def _chunk(self, text: str) -> list[str]:
        max_tokens = settings.chunk_size
        overlap = settings.chunk_overlap
        encoded = self._tokenizer.encode(text)

        if len(encoded) <= max_tokens:
            return [text.strip()] if text.strip() else []

        chunks: list[str] = []
        start = 0
        while start < len(encoded):
            end = min(start + max_tokens, len(encoded))
            chunk_tokens = encoded[start:end]
            chunks.append(self._tokenizer.decode(chunk_tokens).strip())
            if end >= len(encoded):
                break
            start = end - overlap
        return [c for c in chunks if c]
