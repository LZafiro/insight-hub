"""Pydantic schemas for API I/O."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.models import DocumentStatus, MessageRole, UserRole


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Auth ----


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


# ---- Users ----


class UserOut(ORMBase):
    id: UUID
    email: EmailStr
    name: str
    role: UserRole
    workspace_id: UUID
    created_at: datetime


# ---- Documents ----


class DocumentOut(ORMBase):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    error_message: str | None
    created_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentOut]
    total: int


# ---- Chat ----


class Citation(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_name: str
    score: float
    snippet: str


class ChatRequest(BaseModel):
    conversation_id: UUID | None = None
    message: str = Field(..., min_length=1, max_length=4000)


class MessageOut(ORMBase):
    id: UUID
    role: MessageRole
    content: str
    citations: list[Citation] = []
    created_at: datetime


class ConversationOut(ORMBase):
    id: UUID
    title: str
    created_at: datetime
    messages: list[MessageOut] = []


# ---- Health ----


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
