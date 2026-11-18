"""The Claude adapter and the RAG event stream, without calling the API."""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import anthropic
import httpx2
import pytest

from app.modules.llm.answers import (
    SYSTEM_PROMPT,
    AnswerGenerationError,
    Citation,
    ClaudeAnswerGenerator,
    Finished,
    Passage,
    TextDelta,
    build_user_content,
    create_answer_generator,
)
from app.modules.rag.service import (
    NO_SOURCES_ANSWER,
    REFUSED_ANSWER,
    answer_events,
    collect_answer,
)
from app.modules.retrieval.store import SearchHit
from tests.support import ScriptedAnswerGenerator, make_settings

PASSAGES = [Passage("10-K 2025", "Net income was 4.2 billion."), Passage("Q3", "Deposits grew.")]


def test_passages_become_citable_documents_with_the_question_last() -> None:
    content = build_user_content("What was net income?", PASSAGES)
    assert [block["type"] for block in content] == ["document", "document", "text"]
    first: Any = content[0]
    assert first["title"] == "10-K 2025"
    assert first["source"] == {
        "type": "text",
        "media_type": "text/plain",
        "data": "Net income was 4.2 billion.",
    }
    assert first["citations"] == {"enabled": True}
    assert content[-1] == {"type": "text", "text": "What was net income?"}


def _delta(index: int, **delta: Any) -> SimpleNamespace:
    return SimpleNamespace(type="content_block_delta", index=index, delta=SimpleNamespace(**delta))


class _FakeStream:
    def __init__(self, events: list[SimpleNamespace], stop_reason: str = "end_turn") -> None:
        self._events = events
        self._stop_reason = stop_reason

    async def __aenter__(self) -> "_FakeStream":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def __aiter__(self) -> AsyncIterator[SimpleNamespace]:
        for event in self._events:
            yield event

    async def get_final_message(self) -> SimpleNamespace:
        return SimpleNamespace(
            model="claude-opus-5-5",
            stop_reason=self._stop_reason,
            usage=SimpleNamespace(input_tokens=321, output_tokens=45),
        )


class _FakeClient:
    def __init__(self, stream: _FakeStream | Exception) -> None:
        self.requests: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))
        self._result = stream

    def _stream(self, **kwargs: Any) -> _FakeStream:
        self.requests.append(kwargs)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _generator(client: _FakeClient) -> ClaudeAnswerGenerator:
    return ClaudeAnswerGenerator(client, make_settings())  # type: ignore[arg-type]


async def test_claude_stream_is_mapped_to_segments_and_citations() -> None:
    citation = SimpleNamespace(
        type="char_location",
        document_index=1,
        cited_text="Deposits grew.",
        start_char_index=0,
        end_char_index=14,
    )
    client = _FakeClient(
        _FakeStream(
            [
                SimpleNamespace(type="message_start"),
                _delta(0, type="thinking_delta", thinking="..."),
                _delta(1, type="text_delta", text="Yes. "),
                _delta(2, type="citations_delta", citation=citation),
                _delta(2, type="text_delta", text="Deposits "),
                _delta(2, type="text_delta", text="grew."),
                SimpleNamespace(type="message_stop"),
            ]
        )
    )

    events = [e async for e in _generator(client).stream_answer("Did deposits grow?", PASSAGES)]

    assert events == [
        TextDelta(0, "Yes. "),
        Citation(
            segment=1, passage_index=1, cited_text="Deposits grew.", start_char=0, end_char=14
        ),
        TextDelta(1, "Deposits "),
        TextDelta(1, "grew."),
        Finished("claude-opus-5-5", "end_turn", input_tokens=321, output_tokens=45),
    ]

    request = client.requests[0]
    assert request["model"] == "claude-opus-5-5"
    assert request["system"] == SYSTEM_PROMPT
    assert request["output_config"] == {"effort": "medium"}
    assert request["fallbacks"] == "default"
    assert request["betas"] == ["server-side-fallback-2026-07-01"]
    # Current models reject sampling parameters and manual thinking budgets.
    assert not {"temperature", "top_p", "top_k", "thinking"} & request.keys()


async def test_refusal_is_reported_not_treated_as_an_answer() -> None:
    client = _FakeClient(_FakeStream([], stop_reason="refusal"))
    events = [e async for e in _generator(client).stream_answer("q", PASSAGES)]
    assert isinstance(events[-1], Finished)
    assert events[-1].refused


def _api_error(status: int) -> anthropic.APIStatusError:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(status, request=request)
    if status == 429:
        return anthropic.RateLimitError("limited", response=response, body=None)
    return anthropic.APIStatusError("boom", response=response, body=None)


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (_api_error(429), "busy"),
        (_api_error(529), "temporarily unavailable"),
        (_api_error(400), "rejected"),
        (
            anthropic.APIConnectionError(
                request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
            ),
            "could not be reached",
        ),
    ],
)
async def test_api_failures_become_safe_messages(error: Exception, message: str) -> None:
    generator = _generator(_FakeClient(error))
    with pytest.raises(AnswerGenerationError, match=message):
        async for _ in generator.stream_answer("q", PASSAGES):
            pass


# ---------- RAG event stream ----------


def _hit(content: str, *, char_start: int = 0, page: int | None = None) -> SearchHit:
    return SearchHit(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_title="10-K 2025",
        ordinal=0,
        content=content,
        heading="Results",
        page=page,
        char_start=char_start,
        char_end=char_start + len(content),
        score=0.9,
    )


async def test_no_sources_means_no_model_call() -> None:
    generator = ScriptedAnswerGenerator()
    answer = await collect_answer(answer_events(generator, "anything?", []))
    assert generator.calls == []
    assert answer.text == NO_SOURCES_ANSWER
    assert answer.sources == []
    assert answer.done == {"grounded": False, "model": None, "usage": None}


async def test_citations_point_into_the_source_document() -> None:
    text = "Net income was 4.2 billion in 2025, up from 3.9 billion."
    hit = _hit(text, char_start=1000, page=7)
    generator = ScriptedAnswerGenerator()

    events = [e async for e in answer_events(generator, "What was net income?", [hit])]

    assert [e.name for e in events] == ["sources", "delta", "delta", "citation", "delta", "done"]
    assert generator.calls[0][1] == [Passage("10-K 2025", text)]
    citation = events[3].data
    assert citation["segment"] == 1
    assert citation["source"] == 0
    assert citation["document_id"] == str(hit.document_id)
    assert citation["page"] == 7
    assert citation["cited_text"] == text[:30]
    # Chunk-relative positions are shifted by where the chunk starts in the document.
    assert (citation["start_char"], citation["end_char"]) == (1000, 1030)
    assert events[-1].data["grounded"] is True
    assert events[-1].data["usage"] == {"input_tokens": 100, "output_tokens": 20}


async def test_collected_answer_groups_citations_by_segment() -> None:
    hit = _hit("Net income was 4.2 billion in 2025.")
    answer = await collect_answer(answer_events(ScriptedAnswerGenerator(), "q", [hit]))
    assert answer.text == "According to the documents, this is the answer."
    assert [len(s.citations) for s in answer.segments] == [0, 1]
    assert "segment" not in answer.segments[1].citations[0]
    assert answer.sources[0]["chunk_id"] == str(hit.chunk_id)


async def test_refusal_replaces_partial_text() -> None:
    hit = _hit("Net income was 4.2 billion in 2025.")
    answer = await collect_answer(answer_events(ScriptedAnswerGenerator(refuse=True), "q", [hit]))
    assert answer.text == REFUSED_ANSWER
    assert answer.done["grounded"] is False


async def test_a_citation_for_an_unknown_passage_is_dropped() -> None:
    class BadIndex:
        async def stream_answer(self, question: str, passages: Any) -> AsyncIterator[Any]:
            yield TextDelta(0, "Text.")
            yield Citation(segment=0, passage_index=5, cited_text="x", start_char=0, end_char=1)
            yield Finished("m", "end_turn", 1, 1)

    answer = await collect_answer(answer_events(BadIndex(), "q", [_hit("Some text.")]))
    assert answer.segments[0].citations == []
    assert answer.done["grounded"] is False


def _without_ambient_credentials(monkeypatch: pytest.MonkeyPatch, home: Any) -> None:
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    # Keeps a login profile on the developer's machine out of the test.
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))


def test_no_generator_without_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    _without_ambient_credentials(monkeypatch, tmp_path)
    assert create_answer_generator(make_settings()) is None


def test_generator_is_created_from_the_configured_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    _without_ambient_credentials(monkeypatch, tmp_path)
    settings = make_settings(anthropic_api_key="sk-ant-test")
    assert isinstance(create_answer_generator(settings), ClaudeAnswerGenerator)
