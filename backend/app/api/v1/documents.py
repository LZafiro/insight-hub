"""Document endpoints: upload, list."""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import (
    CurrentUser,
    DBSession,
    get_document_repo,
    get_ingestion_service,
)
from app.domain.models import Document, DocumentStatus
from app.domain.schemas import DocumentList, DocumentOut
from app.repositories.documents import DocumentRepository
from app.services.ingestion import IngestionService, UnsupportedContentTypeError

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB
ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain", "text/markdown"}


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    user: CurrentUser,
    db: DBSession,
    file: Annotated[UploadFile, File(...)],
    ingestion: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> DocumentOut:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Content type {file.content_type} not supported",
        )

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large")

    document = Document(
        workspace_id=user.workspace_id,
        uploaded_by=user.id,
        filename=file.filename or "untitled",
        content_type=file.content_type,
        size_bytes=len(raw),
        storage_key=f"local://{uuid4()}",
        status=DocumentStatus.PROCESSING,
    )
    db.add(document)
    await db.flush()

    try:
        await ingestion.ingest(document, raw)
    except UnsupportedContentTypeError as e:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(e)) from e
    except Exception as e:
        # Ingestion already marked the document FAILED; surface the error.
        await db.commit()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Ingestion failed: {e}") from e

    await db.commit()
    await db.refresh(document)
    return DocumentOut.model_validate(document)


@router.get("", response_model=DocumentList)
async def list_documents(
    user: CurrentUser,
    repo: Annotated[DocumentRepository, Depends(get_document_repo)],
    limit: int = 50,
    offset: int = 0,
) -> DocumentList:
    items, total = await repo.list_by_workspace(user.workspace_id, limit=limit, offset=offset)
    return DocumentList(
        items=[DocumentOut.model_validate(d) for d in items],
        total=total,
    )
