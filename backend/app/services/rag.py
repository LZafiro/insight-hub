"""Retrieval-Augmented Generation pipeline."""

from dataclasses import dataclass
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.models import Chunk
from app.domain.schemas import Citation
from app.services.llm import LLMMessage, LLMProvider, LLMResponse
from app.services.reranker import RerankProvider
from app.services.retriever import HybridRetriever

log = get_logger(__name__)


SYSTEM_PROMPT = """\
You are Insight Hub, an internal research assistant.

Rules:
1. Answer ONLY using the provided context excerpts. If the context does not
   contain enough information, respond exactly: "I don't have enough information
   in the provided documents to answer that."
2. Cite every factual claim using the bracket notation matching the excerpt
   number, e.g. "Revenue grew 12% [2]."
3. Be concise. Prefer 3-5 sentences over paragraphs.
4. Never invent information not present in the context.
"""


@dataclass
class RAGResult:
    answer: str
    citations: list[Citation]
    llm: LLMResponse


class RAGService:
    def __init__(
        self,
        retriever: HybridRetriever,
        reranker: RerankProvider,
        llm: LLMProvider,
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._llm = llm

    async def answer(self, query: str, workspace_id: UUID) -> RAGResult:
        candidates = await self._retriever.retrieve(
            query, workspace_id, candidate_k=settings.retrieval_candidate_k
        )
        chunks = await self._reranker.rerank(query, candidates, top_k=settings.retrieval_top_k)

        log.info(
            "rag.retrieved",
            workspace_id=str(workspace_id),
            candidates=len(candidates),
            reranked=len(chunks),
        )

        if not chunks:
            return RAGResult(
                answer="I don't have enough information in the provided documents to answer that.",
                citations=[],
                llm=LLMResponse(content="", input_tokens=0, output_tokens=0, model=settings.llm_model),
            )

        context, citations = self._build_context(chunks)
        messages = [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=f"Context excerpts:\n\n{context}\n\nQuestion: {query}",
            ),
        ]
        response = await self._llm.complete(messages, temperature=0.2)
        return RAGResult(answer=response.content, citations=citations, llm=response)

    @staticmethod
    def _build_context(chunks: list[Chunk]) -> tuple[str, list[Citation]]:
        excerpts: list[str] = []
        citations: list[Citation] = []
        n = len(chunks)
        for idx, chunk in enumerate(chunks, start=1):
            excerpts.append(f"[{idx}] {chunk.content}")
            doc_name = chunk.document.filename if chunk.document else "unknown"
            citations.append(
                Citation(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_name=doc_name,
                    score=round(1.0 - (idx - 1) / n, 4),
                    snippet=chunk.content[:200],
                )
            )
        return "\n\n".join(excerpts), citations
