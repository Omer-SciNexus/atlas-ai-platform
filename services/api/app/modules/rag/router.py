import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.deps import CurrentPrincipal, TenantSession, require
from app.core.rbac import Permission
from app.modules.audit import service as audit
from app.modules.llm.answers import AnswerGenerationError, AnswerGenerator
from app.modules.rag import service
from app.modules.rag.service import StreamEvent
from app.modules.retrieval.store import SearchHit

router = APIRouter(prefix="/v1", tags=["rag"])
log = structlog.get_logger(__name__)

_READ = Depends(require(Permission.DOCUMENTS_READ))


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=50)


class SourceOut(BaseModel):
    index: int
    chunk_id: UUID
    document_id: UUID
    document_title: str
    heading: str | None
    page: int | None
    score: float
    content: str


class SearchResponse(BaseModel):
    results: list[SourceOut]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    stream: bool = Field(
        default=True,
        description="true: server-sent events as the answer is written. false: one JSON body.",
    )


class CitationOut(BaseModel):
    source: int = Field(description="Index into `sources`.")
    document_id: UUID
    document_title: str
    page: int | None
    cited_text: str
    start_char: int
    end_char: int


class SegmentOut(BaseModel):
    text: str
    citations: list[CitationOut]


class AskResponse(BaseModel):
    answer: str
    segments: list[SegmentOut]
    sources: list[SourceOut]
    grounded: bool = Field(description="True when at least one statement cites a source.")
    model: str | None
    usage: dict[str, int] | None


async def _retrieve(
    request: Request, session: TenantSession, query: str, top_k: int | None
) -> list[SearchHit]:
    settings = request.app.state.settings
    return await service.retrieve(
        session,
        request.app.state.embedder,
        request.app.state.vector_store,
        query,
        top_k=top_k or settings.retrieval_top_k,
        min_score=settings.retrieval_min_score,
    )


@router.post("/search", response_model=SearchResponse, dependencies=[_READ])
async def search(request: Request, session: TenantSession, body: SearchRequest) -> SearchResponse:
    """Retrieval only: the passages most similar to the query, best first. No model call."""
    hits = await _retrieve(request, session, body.query, body.top_k)
    return SearchResponse(
        results=[SourceOut(**service.source_payload(i, h)) for i, h in enumerate(hits)]
    )


def _sse(event: StreamEvent) -> str:
    return f"event: {event.name}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"


async def _sse_stream(events: AsyncIterator[StreamEvent]) -> AsyncIterator[str]:
    try:
        async for event in events:
            yield _sse(event)
    except AnswerGenerationError as exc:
        # The 200 response has already started, so the failure is reported in the stream.
        yield _sse(StreamEvent("error", {"detail": str(exc)}))
    except Exception:
        log.exception("rag.stream_failed")
        yield _sse(StreamEvent("error", {"detail": "Internal server error"}))


_SSE_EXAMPLE = (
    'event: sources\ndata: {"sources": [...]}\n\n'
    'event: delta\ndata: {"segment": 0, "text": "Revenue rose 12%"}\n\n'
    'event: citation\ndata: {"segment": 0, "source": 2, "cited_text": "...", ...}\n\n'
    'event: done\ndata: {"grounded": true, "model": "...", "usage": {...}}\n\n'
)


@router.post(
    "/ask",
    response_model=AskResponse,
    dependencies=[_READ],
    responses={
        200: {"content": {"text/event-stream": {"example": _SSE_EXAMPLE}}},
        503: {"description": "Answer generation is not configured or the model is unavailable."},
    },
)
async def ask(
    request: Request, principal: CurrentPrincipal, session: TenantSession, body: AskRequest
) -> Any:
    """Answer a question from the tenant's documents, with citations.

    Events when streaming: ``sources`` (the retrieved passages), then ``delta`` (answer text)
    and ``citation`` (a quote from a source that supports one segment of the answer), then
    ``done``. On failure after the stream has started: ``error``.
    """
    generator: AnswerGenerator | None = request.app.state.answer_generator
    if generator is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Answer generation is not configured (set ATLAS_ANTHROPIC_API_KEY)",
        )

    hits = await _retrieve(request, session, body.question, body.top_k)
    # The question text is not stored here: it can hold personal data, and the audit log is
    # append-only. The audit event records that a question was asked and what it retrieved.
    await audit.record(
        session,
        principal,
        "rag.asked",
        details={
            "question_chars": len(body.question),
            "chunk_ids": [str(h.chunk_id) for h in hits],
        },
    )
    events = service.answer_events(generator, body.question, hits)

    if body.stream:
        return StreamingResponse(
            _sse_stream(events),
            media_type="text/event-stream",
            # Tell proxies (nginx, ALB) not to buffer or cache the stream.
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        answer = await service.collect_answer(events)
    except AnswerGenerationError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from None
    return AskResponse(
        answer=answer.text,
        segments=[
            SegmentOut(text=s.text, citations=[CitationOut(**c) for c in s.citations])
            for s in answer.segments
        ],
        sources=[SourceOut(**s) for s in answer.sources],
        grounded=bool(answer.done.get("grounded")),
        model=answer.done.get("model"),
        usage=answer.done.get("usage"),
    )
