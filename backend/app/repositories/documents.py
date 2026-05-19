"""Document repository."""

from uuid import UUID

from sqlalchemy import func, select

from app.domain.models import Document
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    model = Document

    async def list_by_workspace(
        self, workspace_id: UUID, limit: int = 50, offset: int = 0
    ) -> tuple[list[Document], int]:
        stmt = (
            select(Document)
            .where(Document.workspace_id == workspace_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        count_stmt = select(func.count()).select_from(Document).where(
            Document.workspace_id == workspace_id
        )

        result = await self.session.execute(stmt)
        total = (await self.session.execute(count_stmt)).scalar_one()
        return list(result.scalars().all()), total
