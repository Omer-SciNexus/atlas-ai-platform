"""The ingestion pipeline: claim a job, then parse, chunk, embed and store one document.

Jobs are rows in Postgres, claimed with ``FOR UPDATE SKIP LOCKED`` so several workers can
run without taking the same job. The queue lives in the same database as the documents, so
"document row created" and "job queued" commit together (see docs/adr/0005).

No database transaction is held open while the file is parsed or the embedding API is
called. Those steps can take many seconds, and a transaction open that long would pin a
connection and block vacuum.
"""

import asyncio
from dataclasses import dataclass
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.db import tenant_session
from app.modules.audit import service as audit
from app.modules.documents.blobs import BlobNotFoundError, BlobStore, blob_key
from app.modules.documents.models import Document
from app.modules.ingestion.chunker import Chunk, chunk_blocks
from app.modules.ingestion.parsers import DocumentParseError, UnsupportedFileTypeError, parse
from app.modules.llm.embeddings import Embedder
from app.modules.retrieval.store import ChunkRecord, VectorStore

log = structlog.get_logger(__name__)

WORKER_ACTOR = "ingestion-worker"


@dataclass(frozen=True, slots=True)
class IngestionDeps:
    settings: Settings
    sessionmaker: async_sessionmaker[AsyncSession]
    blobs: BlobStore
    embedder: Embedder
    vectors: VectorStore


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    id: int
    tenant_id: UUID
    document_id: UUID
    attempts: int


class PermanentIngestionError(Exception):
    """Retrying cannot help. The message is shown to the user on the document."""


# One statement: pick the oldest runnable job that no other worker holds, and mark it running.
# A job stuck in "running" past the lock timeout belonged to a worker that died; take it over.
_CLAIM = text(
    """
    UPDATE ingestion_jobs
       SET status = 'running', locked_at = now(), attempts = attempts + 1
     WHERE id = (
            SELECT id
              FROM ingestion_jobs
             WHERE (status = 'queued' AND run_after <= now())
                OR (status = 'running' AND locked_at < now() - make_interval(secs => :timeout))
             ORDER BY id
               FOR UPDATE SKIP LOCKED
             LIMIT 1
           )
    RETURNING id, tenant_id, document_id, attempts
    """
)


async def claim_job(deps: IngestionDeps) -> ClaimedJob | None:
    async with deps.sessionmaker() as session, session.begin():
        row = (
            await session.execute(_CLAIM, {"timeout": deps.settings.ingestion_lock_timeout_seconds})
        ).first()
    if row is None:
        return None
    return ClaimedJob(row.id, row.tenant_id, row.document_id, row.attempts)


async def _finish_job(deps: IngestionDeps, job_id: int, *, status: str, error: str | None) -> None:
    async with deps.sessionmaker() as session, session.begin():
        await session.execute(
            text(
                "UPDATE ingestion_jobs SET status = :status, last_error = :error, "
                "locked_at = NULL, finished_at = now() WHERE id = :id"
            ),
            {"id": job_id, "status": status, "error": error},
        )


async def _retry_job(deps: IngestionDeps, job: ClaimedJob, error: str) -> None:
    delay_seconds = min(5 * 2**job.attempts, 300)
    async with deps.sessionmaker() as session, session.begin():
        await session.execute(
            text(
                "UPDATE ingestion_jobs SET status = 'queued', last_error = :error, "
                "locked_at = NULL, run_after = now() + make_interval(secs => :delay) "
                "WHERE id = :id"
            ),
            {"id": job.id, "error": error, "delay": delay_seconds},
        )


async def _set_document_state(
    deps: IngestionDeps, job: ClaimedJob, *, status: str, error: str | None
) -> Document | None:
    async with tenant_session(deps.sessionmaker, job.tenant_id) as session:
        document = await session.get(Document, job.document_id, with_for_update=True)
        if document is not None:
            document.status = status
            document.error = error
            if status == "failed":
                await audit.record_system(
                    session,
                    job.tenant_id,
                    WORKER_ACTOR,
                    "document.ingestion_failed",
                    resource_type="document",
                    resource_id=str(job.document_id),
                    details={"error": error, "attempts": job.attempts},
                )
        return document


def _embedding_input(title: str, chunk: Chunk) -> str:
    """Give the embedding model the context a reader would have.

    A chunk like "It rose 12% over the prior year." says nothing on its own. With the
    document title and section heading in front, its vector lands near the right questions.
    Only the vector uses this text; the stored chunk content stays the exact source text.
    """
    return "\n".join(part for part in (title, chunk.heading, chunk.content) if part)


async def ingest_document(deps: IngestionDeps, job: ClaimedJob) -> int | None:
    """Run the pipeline for one document. Returns the chunk count, or None if it was deleted."""
    document = await _set_document_state(deps, job, status="processing", error=None)
    if document is None:
        return None
    title, mime_type = document.title, document.mime_type

    try:
        data = await deps.blobs.get(blob_key(job.tenant_id, job.document_id))
    except BlobNotFoundError:
        raise PermanentIngestionError("The uploaded file is missing from storage") from None

    try:
        # Parsing a large PDF is CPU work; keep it off the event loop.
        blocks = await asyncio.to_thread(parse, data, mime_type)
    except (DocumentParseError, UnsupportedFileTypeError) as exc:
        raise PermanentIngestionError(str(exc)) from None

    chunks = chunk_blocks(
        blocks, size=deps.settings.chunk_size_chars, overlap=deps.settings.chunk_overlap_chars
    )
    embeddings = await deps.embedder.embed_documents([_embedding_input(title, c) for c in chunks])
    records = [
        ChunkRecord(c.ordinal, c.content, c.heading, c.page, c.char_start, c.char_end, e)
        for c, e in zip(chunks, embeddings, strict=True)
    ]

    async with tenant_session(deps.sessionmaker, job.tenant_id) as session:
        # Lock the row: if the user deleted the document while we worked, stop here.
        document = await session.get(Document, job.document_id, with_for_update=True)
        if document is None:
            return None
        await deps.vectors.replace_document(
            session,
            tenant_id=job.tenant_id,
            document_id=job.document_id,
            embedding_model=deps.embedder.model,
            records=records,
        )
        document.status = "ready"
        document.error = None
        document.chunk_count = len(records)
        await audit.record_system(
            session,
            job.tenant_id,
            WORKER_ACTOR,
            "document.ingested",
            resource_type="document",
            resource_id=str(job.document_id),
            details={"chunks": len(records), "embedding_model": deps.embedder.model},
        )
    return len(records)


async def run_job(deps: IngestionDeps, job: ClaimedJob) -> None:
    structlog.contextvars.bind_contextvars(
        job_id=job.id, tenant_id=str(job.tenant_id), document_id=str(job.document_id)
    )
    try:
        if job.attempts > deps.settings.ingestion_max_attempts:
            # Only reachable when workers keep dying mid-job (the job is taken over each
            # time the lock expires). Stop here, or it would be taken over forever.
            raise PermanentIngestionError("Ingestion did not finish; the file may be too large")
        chunk_count = await ingest_document(deps, job)
    except PermanentIngestionError as exc:
        log.warning("ingestion.failed", reason=str(exc))
        await _set_document_state(deps, job, status="failed", error=str(exc))
        await _finish_job(deps, job.id, status="failed", error=type(exc).__name__)
    except Exception as exc:
        error = type(exc).__name__
        if job.attempts >= deps.settings.ingestion_max_attempts:
            log.exception("ingestion.failed", attempts=job.attempts)
            message = f"Ingestion failed after {job.attempts} attempts"
            await _set_document_state(deps, job, status="failed", error=message)
            await _finish_job(deps, job.id, status="failed", error=error)
        else:
            log.warning("ingestion.retry", error=error, attempts=job.attempts)
            await _retry_job(deps, job, error)
    else:
        await _finish_job(deps, job.id, status="done", error=None)
        log.info("ingestion.done", chunks=chunk_count)
    finally:
        structlog.contextvars.unbind_contextvars("job_id", "tenant_id", "document_id")


async def process_next_job(deps: IngestionDeps) -> bool:
    """Claim and run one job. Returns False when the queue is empty."""
    job = await claim_job(deps)
    if job is None:
        return False
    await run_job(deps, job)
    return True
