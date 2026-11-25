import base64
import binascii
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from uuid import UUID

from sqlalchemy import delete, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.documents.blobs import BlobStore, blob_key
from app.modules.documents.models import Document, IngestionJob
from app.modules.ingestion.parsers import detect_mime_type


class InvalidCursorError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class UploadResult:
    document: Document
    created: bool


_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def safe_filename(raw: str | None) -> str:
    """Keep only the last path component, without control characters."""
    name = PurePosixPath((raw or "").replace("\\", "/")).name
    name = _CONTROL_CHARS.sub("", name).strip()
    return name[:255] or "document"


def default_title(filename: str) -> str:
    stem = PurePosixPath(filename).stem
    return (re.sub(r"[_\-]+", " ", stem).strip() or filename)[:300]


async def create_document(
    session: AsyncSession,
    blobs: BlobStore,
    principal: Principal,
    *,
    user_id: UUID,
    filename: str,
    title: str | None,
    data: bytes,
) -> UploadResult:
    """Store an upload and queue it for ingestion.

    The document row, the job and the audit event are written in one transaction, so there
    is never a document without a job. Uploading the same bytes again returns the existing
    document instead of a duplicate.
    """
    mime_type = detect_mime_type(filename, data[:2048])
    sha256 = hashlib.sha256(data).hexdigest()

    stmt = (
        insert(Document)
        .values(
            tenant_id=principal.tenant_id,
            title=(title or "").strip()[:300] or default_title(filename),
            filename=filename,
            mime_type=mime_type,
            sha256=sha256,
            size_bytes=len(data),
            created_by=user_id,
        )
        # A concurrent upload of the same file must not fail with a constraint error.
        .on_conflict_do_nothing(index_elements=[Document.tenant_id, Document.sha256])
        .returning(Document)
    )
    document = (await session.execute(stmt)).scalar_one_or_none()
    if document is None:
        existing = (await session.scalars(select(Document).where(Document.sha256 == sha256))).one()
        return UploadResult(existing, created=False)

    # If this write fails the transaction rolls back. If the commit fails after it, the
    # file is left without a row, which is harmless: nothing can reach it.
    await blobs.put(blob_key(principal.tenant_id, document.id), data)
    session.add(IngestionJob(tenant_id=principal.tenant_id, document_id=document.id))
    await audit.record(
        session,
        principal,
        "document.uploaded",
        actor_user_id=user_id,
        resource_type="document",
        resource_id=str(document.id),
        details={"filename": filename, "mime_type": mime_type, "size_bytes": len(data)},
    )
    return UploadResult(document, created=True)


def _encode_cursor(document: Document) -> str:
    raw = f"{document.created_at.isoformat()}|{document.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        created_at, document_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(created_at), UUID(document_id)
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise InvalidCursorError from None


async def list_documents(
    session: AsyncSession, limit: int, cursor: str | None
) -> tuple[list[Document], str | None]:
    """Newest first, paged by (created_at, id) so new uploads never shift a page."""
    stmt = select(Document).order_by(Document.created_at.desc(), Document.id.desc())
    if cursor is not None:
        stmt = stmt.where(tuple_(Document.created_at, Document.id) < _decode_cursor(cursor))
    rows = list((await session.scalars(stmt.limit(limit + 1))).all())
    if len(rows) <= limit:
        return rows, None
    return rows[:limit], _encode_cursor(rows[limit - 1])


async def get_document(session: AsyncSession, document_id: UUID) -> Document | None:
    # Row-level security makes another tenant's document id look like it does not exist.
    return await session.get(Document, document_id)


async def delete_document(
    session: AsyncSession, principal: Principal, document_id: UUID
) -> Document | None:
    """Delete the row; its chunks and jobs go with it (foreign keys cascade).

    The caller removes the stored file after the transaction commits.
    """
    document = (
        await session.execute(
            delete(Document).where(Document.id == document_id).returning(Document)
        )
    ).scalar_one_or_none()
    if document is None:
        return None
    await audit.record(
        session,
        principal,
        "document.deleted",
        resource_type="document",
        resource_id=str(document_id),
        details={"filename": document.filename, "sha256": document.sha256},
    )
    return document
