"""Chunk repository: vector similarity and full-text search."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.domain.models import Chunk
from app.repositories.base import BaseRepository


class ChunkRepository(BaseRepository[Chunk]):
    model = Chunk

    async def search_dense(
        self,
        query_embedding: list[float],
        workspace_id: UUID,
        top_n: int = 20,
    ) -> list[tuple[Chunk, float]]:
        distance = Chunk.embedding.cosine_distance(query_embedding)
        stmt = (
            select(Chunk, (1 - distance).label("score"))
            .where(Chunk.workspace_id == workspace_id)
            .order_by(distance)
            .limit(top_n)
            .options(selectinload(Chunk.document))
        )
        result = await self.session.execute(stmt)
        return [(row[0], float(row[1])) for row in result.all()]

    async def search_bm25(
        self,
        query: str,
        workspace_id: UUID,
        top_n: int = 20,
    ) -> list[tuple[Chunk, float]]:
        tsquery = func.plainto_tsquery("english", query)
        rank = func.ts_rank(Chunk.content_tsv, tsquery)
        stmt = (
            select(Chunk, rank.label("score"))
            .where(Chunk.workspace_id == workspace_id, Chunk.content_tsv.op("@@")(tsquery))
            .order_by(rank.desc())
            .limit(top_n)
            .options(selectinload(Chunk.document))
        )
        result = await self.session.execute(stmt)
        return [(row[0], float(row[1])) for row in result.all()]

    async def bulk_insert(self, chunks: list[Chunk]) -> None:
        self.session.add_all(chunks)
        await self.session.flush()
