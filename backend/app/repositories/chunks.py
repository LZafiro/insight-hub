"""Chunk repository: stores embeddings and performs vector similarity search."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domain.models import Chunk
from app.repositories.base import BaseRepository


class ChunkRepository(BaseRepository[Chunk]):
    model = Chunk

    async def search_similar(
        self,
        query_embedding: list[float],
        workspace_id: UUID,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[tuple[Chunk, float]]:
        """Return top-k chunks ranked by cosine similarity within a workspace.

        Returns tuples of (chunk, similarity_score). Similarity is computed
        as ``1 - cosine_distance`` so higher is better. Filters by ``min_score``
        to drop irrelevant matches.
        """
        # pgvector cosine distance operator is ``<=>`` (0 = identical, 2 = opposite).
        distance = Chunk.embedding.cosine_distance(query_embedding)
        stmt = (
            select(Chunk, (1 - distance).label("score"))
            .where(Chunk.workspace_id == workspace_id)
            .order_by(distance)
            .limit(top_k)
            .options(selectinload(Chunk.document))
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [(row[0], float(row[1])) for row in rows if float(row[1]) >= min_score]

    async def bulk_insert(self, chunks: list[Chunk]) -> None:
        self.session.add_all(chunks)
        await self.session.flush()
