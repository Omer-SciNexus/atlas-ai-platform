"""Vector storage and search.

``VectorStore`` is the interface; ``PgVectorStore`` keeps vectors in Postgres with pgvector.
Keeping them in the same database as everything else means tenant isolation is the same
row-level security policy as every other table, and a document and its chunks change in one
transaction. A dedicated vector database can implement the same interface later.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import Document, DocumentChunk


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    ordinal: int
    content: str
    heading: str | None
    page: int | None
    char_start: int
    char_end: int
    embedding: list[float]


@dataclass(frozen=True, slots=True)
class SearchHit:
    chunk_id: UUID
    document_id: UUID
    document_title: str
    ordinal: int
    content: str
    heading: str | None
    page: int | None
    char_start: int
    char_end: int
    score: float  # cosine similarity, 1.0 = same direction


class VectorStore(Protocol):
    async def replace_document(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        document_id: UUID,
        embedding_model: str,
        records: Sequence[ChunkRecord],
    ) -> None: ...

    async def search(
        self, session: AsyncSession, embedding: Sequence[float], *, top_k: int, min_score: float
    ) -> list[SearchHit]: ...


class PgVectorStore:
    INSERT_BATCH = 200

    async def replace_document(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        document_id: UUID,
        embedding_model: str,
        records: Sequence[ChunkRecord],
    ) -> None:
        """Swap all chunks of one document inside the caller's transaction."""
        await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        rows = [
            {
                "tenant_id": tenant_id,
                "document_id": document_id,
                "ordinal": r.ordinal,
                "content": r.content,
                "heading": r.heading,
                "page": r.page,
                "char_start": r.char_start,
                "char_end": r.char_end,
                "embedding": r.embedding,
                "embedding_model": embedding_model,
            }
            for r in records
        ]
        for start in range(0, len(rows), self.INSERT_BATCH):
            await session.execute(insert(DocumentChunk), rows[start : start + self.INSERT_BATCH])

    async def search(
        self, session: AsyncSession, embedding: Sequence[float], *, top_k: int, min_score: float
    ) -> list[SearchHit]:
        # The HNSW index returns the nearest vectors across all tenants, and row-level
        # security then removes the other tenants' rows. Without iterative scans, a small
        # tenant could get fewer than top_k results (or none) although it has matches.
        # With them, the index keeps scanning until enough visible rows are found.
        await session.execute(
            text("SELECT set_config('hnsw.iterative_scan', 'strict_order', true)")
        )
        distance = DocumentChunk.embedding.cosine_distance(embedding)
        stmt = (
            select(DocumentChunk, Document.title, distance.label("distance"))
            .join(Document, Document.id == DocumentChunk.document_id)
            # Old chunks stay in place while a document is re-ingested; do not serve them.
            .where(Document.status == "ready")
            .order_by(distance)
            .limit(top_k)
        )
        hits: list[SearchHit] = []
        for chunk, title, dist in (await session.execute(stmt)).all():
            score = 1.0 - float(dist)
            if score < min_score:
                break  # ordered by distance, so every later row scores lower
            hits.append(
                SearchHit(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_title=title,
                    ordinal=chunk.ordinal,
                    content=chunk.content,
                    heading=chunk.heading,
                    page=chunk.page,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    score=round(score, 6),
                )
            )
        return hits
