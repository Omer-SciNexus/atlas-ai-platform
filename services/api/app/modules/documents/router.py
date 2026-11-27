from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict

from app.core.deps import CurrentPrincipal, TenantSession, require
from app.core.rbac import Permission
from app.modules.documents import service
from app.modules.documents.blobs import BlobStore, blob_key
from app.modules.ingestion.parsers import UnsupportedFileTypeError
from app.modules.tenants.service import sync_current_user

router = APIRouter(prefix="/v1/documents", tags=["documents"])
log = structlog.get_logger(__name__)

_READ = Depends(require(Permission.DOCUMENTS_READ))
_WRITE = Depends(require(Permission.DOCUMENTS_WRITE))


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    filename: str
    mime_type: str
    size_bytes: int
    status: Literal["pending", "processing", "ready", "failed"]
    error: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class DocumentPage(BaseModel):
    items: list[DocumentOut]
    next_cursor: str | None


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    """Read the upload, stopping as soon as it is over the limit."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"File is larger than the {limit // (1024 * 1024)} MB limit",
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def _delete_blob(blobs: BlobStore, key: str) -> None:
    try:
        await blobs.delete(key)
    except OSError:
        # The row is already gone, so the file is unreachable; it only wastes space.
        log.warning("documents.blob_delete_failed", key=key)


@router.post(
    "",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_WRITE],
    responses={200: {"description": "The same file was already uploaded; it is returned."}},
)
async def upload_document(
    request: Request,
    response: Response,
    principal: CurrentPrincipal,
    session: TenantSession,
    file: UploadFile,
    title: Annotated[str | None, Form(max_length=300)] = None,
) -> DocumentOut:
    """Upload a file (.txt, .md, .html, .pdf). Ingestion runs in the background:
    poll ``GET /v1/documents/{id}`` until ``status`` is ``ready`` or ``failed``."""
    settings = request.app.state.settings
    data = await _read_limited(file, settings.max_upload_bytes)
    if not data.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "File is empty")

    current = await sync_current_user(session, principal)
    try:
        result = await service.create_document(
            session,
            request.app.state.blob_store,
            principal,
            user_id=current.user.id,
            filename=service.safe_filename(file.filename),
            title=title,
            data=data,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from None

    if not result.created:
        response.status_code = status.HTTP_200_OK
    return DocumentOut.model_validate(result.document)


@router.get("", response_model=DocumentPage, dependencies=[_READ])
async def list_documents(
    session: TenantSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> DocumentPage:
    try:
        documents, next_cursor = await service.list_documents(session, limit, cursor)
    except service.InvalidCursorError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid cursor") from None
    return DocumentPage(
        items=[DocumentOut.model_validate(d) for d in documents], next_cursor=next_cursor
    )


@router.get("/{document_id}", response_model=DocumentOut, dependencies=[_READ])
async def get_document(session: TenantSession, document_id: UUID) -> DocumentOut:
    document = await service.get_document(session, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return DocumentOut.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_WRITE])
async def delete_document(
    request: Request,
    background: BackgroundTasks,
    principal: CurrentPrincipal,
    session: TenantSession,
    document_id: UUID,
) -> None:
    document = await service.delete_document(session, principal, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    # Runs after the response, so after the transaction has committed: the file is only
    # removed once the row is really gone.
    background.add_task(
        _delete_blob, request.app.state.blob_store, blob_key(principal.tenant_id, document_id)
    )
