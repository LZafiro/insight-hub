from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.models import Chunk
from app.services.llm import LLMResponse
from app.services.rag import RAGService


@pytest.fixture
def fake_workspace_id():
    return uuid4()


@pytest.fixture
def fake_chunk(fake_workspace_id):
    chunk = Chunk(
        document_id=uuid4(),
        workspace_id=fake_workspace_id,
        ordinal=0,
        content="Revenue grew 12% year over year in Q3.",
        embedding=[0.0] * 1536,
        token_count=10,
    )
    chunk.id = uuid4()
    chunk.document = None
    return chunk


async def test_rag_returns_refusal_when_no_matches(fake_workspace_id):
    retriever = AsyncMock()
    retriever.retrieve.return_value = []
    reranker = AsyncMock()
    reranker.rerank.return_value = []
    llm = AsyncMock()

    rag = RAGService(retriever=retriever, reranker=reranker, llm=llm)
    result = await rag.answer("What was Q3 revenue?", workspace_id=fake_workspace_id)

    assert "don't have enough information" in result.answer.lower()
    assert result.citations == []
    llm.complete.assert_not_called()


async def test_rag_returns_answer_with_citations(fake_workspace_id, fake_chunk):
    retriever = AsyncMock()
    retriever.retrieve.return_value = [fake_chunk]
    reranker = AsyncMock()
    reranker.rerank.return_value = [fake_chunk]
    llm = AsyncMock()
    llm.complete.return_value = LLMResponse(
        content="Revenue grew 12% [1].",
        input_tokens=120,
        output_tokens=15,
        model="gpt-4o-mini",
    )

    rag = RAGService(retriever=retriever, reranker=reranker, llm=llm)
    result = await rag.answer("What was Q3 revenue?", workspace_id=fake_workspace_id)

    assert result.answer == "Revenue grew 12% [1]."
    assert len(result.citations) == 1
    assert result.citations[0].score == 1.0
    llm.complete.assert_called_once()
