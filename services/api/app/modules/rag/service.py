"""Retrieval-augmented answering: find passages, then have the model answer from them.

This is plain Python on purpose (no agent framework): the flow is fixed, so a framework
would only hide it. Agents, where the model picks the next step, come in Phase 4.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.llm.answers import AnswerGenerator, Citation, Finished, Passage, TextDelta
from app.modules.llm.embeddings import Embedder
from app.modules.retrieval.store import SearchHit, VectorStore

log = structlog.get_logger(__name__)

NO_SOURCES_ANSWER = (
    "I could not find anything about this in your documents. "
    "Try other words, or upload a document that covers it."
)
REFUSED_ANSWER = "I can't help with this request."


async def retrieve(
    session: AsyncSession,
    embedder: Embedder,
    vectors: VectorStore,
    query: str,
    *,
    top_k: int,
    min_score: float,
) -> list[SearchHit]:
    embedding = await embedder.embed_query(query)
    return await vectors.search(session, embedding, top_k=top_k, min_score=min_score)


def source_payload(index: int, hit: SearchHit) -> dict[str, Any]:
    return {
        "index": index,
        "chunk_id": str(hit.chunk_id),
        "document_id": str(hit.document_id),
        "document_title": hit.document_title,
        "heading": hit.heading,
        "page": hit.page,
        "score": hit.score,
        "content": hit.content,
    }


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """One server-sent event: ``name`` is the event type, ``data`` its JSON body."""

    name: str
    data: dict[str, Any]


def _citation_payload(citation: Citation, hits: Sequence[SearchHit]) -> dict[str, Any]:
    hit = hits[citation.passage_index]
    return {
        "segment": citation.segment,
        "source": citation.passage_index,
        "document_id": str(hit.document_id),
        "document_title": hit.document_title,
        "page": hit.page,
        "cited_text": citation.cited_text,
        # Position in the document's extracted text, so a viewer can highlight the quote.
        "start_char": hit.char_start + citation.start_char,
        "end_char": hit.char_start + citation.end_char,
    }


async def answer_events(
    generator: AnswerGenerator, question: str, hits: Sequence[SearchHit]
) -> AsyncIterator[StreamEvent]:
    """Yield the answer as events: ``sources``, then ``delta`` / ``citation``, then ``done``.

    The answer is a list of segments. A ``delta`` adds text to a segment and a ``citation``
    attaches a source quote to one, so a client can render "text [1]" without parsing
    markers out of the text.
    """
    yield StreamEvent("sources", {"sources": [source_payload(i, h) for i, h in enumerate(hits)]})

    if not hits:
        # Nothing to ground an answer on: do not call the model at all.
        yield StreamEvent("delta", {"segment": 0, "text": NO_SOURCES_ANSWER})
        yield StreamEvent("done", {"grounded": False, "model": None, "usage": None})
        return

    passages = [Passage(title=h.document_title, text=h.content) for h in hits]
    cited = False
    async for event in generator.stream_answer(question, passages):
        if isinstance(event, TextDelta):
            yield StreamEvent("delta", {"segment": event.segment, "text": event.text})
        elif isinstance(event, Citation):
            if not 0 <= event.passage_index < len(hits):
                log.warning("rag.citation_out_of_range", index=event.passage_index)
                continue
            cited = True
            yield StreamEvent("citation", _citation_payload(event, hits))
        elif isinstance(event, Finished):
            if event.refused:
                yield StreamEvent("refusal", {"text": REFUSED_ANSWER})
            log.info(
                "rag.answered",
                model=event.model,
                stop_reason=event.stop_reason,
                input_tokens=event.input_tokens,
                output_tokens=event.output_tokens,
                sources=len(hits),
                cited=cited,
            )
            yield StreamEvent(
                "done",
                {
                    "grounded": cited and not event.refused,
                    "model": event.model,
                    "stop_reason": event.stop_reason,
                    "usage": {
                        "input_tokens": event.input_tokens,
                        "output_tokens": event.output_tokens,
                    },
                },
            )


@dataclass(slots=True)
class Segment:
    text: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class Answer:
    segments: list[Segment] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    done: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.segments)


async def collect_answer(events: AsyncIterator[StreamEvent]) -> Answer:
    """Fold the event stream into one answer, for clients that do not want streaming."""
    answer = Answer()

    def segment(index: int) -> Segment:
        while len(answer.segments) <= index:
            answer.segments.append(Segment())
        return answer.segments[index]

    async for event in events:
        if event.name == "sources":
            answer.sources = event.data["sources"]
        elif event.name == "delta":
            segment(event.data["segment"]).text += event.data["text"]
        elif event.name == "citation":
            data = dict(event.data)
            segment(data.pop("segment")).citations.append(data)
        elif event.name == "refusal":
            # Text streamed before a refusal is partial; replace it.
            answer.segments = [Segment(text=event.data["text"])]
        elif event.name == "done":
            answer.done = event.data
    return answer
