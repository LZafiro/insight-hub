"""Chat endpoint: ask a question, get an answer with citations."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, get_rag_service
from app.domain.schemas import ChatRequest, MessageOut
from app.domain.models import MessageRole
from app.services.rag import RAGService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=MessageOut)
async def chat(
    payload: ChatRequest,
    user: CurrentUser,
    rag: Annotated[RAGService, Depends(get_rag_service)],
) -> MessageOut:
    result = await rag.answer(query=payload.message, workspace_id=user.workspace_id)

    from uuid import uuid4
    from datetime import UTC, datetime

    return MessageOut(
        id=uuid4(),
        role=MessageRole.ASSISTANT,
        content=result.answer,
        citations=result.citations,
        created_at=datetime.now(UTC),
    )
