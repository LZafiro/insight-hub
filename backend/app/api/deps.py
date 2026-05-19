"""Reusable FastAPI dependencies: auth, sessions, services."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import TokenError, decode_token
from app.domain.models import User
from app.repositories.chunks import ChunkRepository
from app.repositories.documents import DocumentRepository
from app.services.embeddings import build_embedding_provider
from app.services.ingestion import IngestionService
from app.services.llm import build_llm_provider
from app.services.rag import RAGService
from app.services.reranker import CrossEncoderReranker, RerankProvider
from app.services.retriever import HybridRetriever

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: DBSession,
) -> User:
    """Resolve the current authenticated user from a bearer token.

    Raises 401 on missing/invalid token, 404 if the user vanished.
    """
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_token(token, expected_type="access")
    except TokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing subject")

    user = await db.get(User, UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ---- Service factories ----


def get_reranker(request: Request) -> RerankProvider:
    return request.app.state.reranker  # type: ignore[no-any-return]


def get_rag_service(
    db: DBSession,
    reranker: Annotated[RerankProvider, Depends(get_reranker)],
) -> RAGService:
    return RAGService(
        retriever=HybridRetriever(
            chunk_repo=ChunkRepository(db),
            embeddings=build_embedding_provider(),
        ),
        reranker=reranker,
        llm=build_llm_provider(),
    )


def get_ingestion_service(db: DBSession) -> IngestionService:
    return IngestionService(
        chunk_repo=ChunkRepository(db),
        embeddings=build_embedding_provider(),
    )


def get_document_repo(db: DBSession) -> DocumentRepository:
    return DocumentRepository(db)
