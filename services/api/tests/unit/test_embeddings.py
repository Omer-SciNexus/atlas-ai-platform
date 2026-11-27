import json
import math
from typing import Any

import httpx
import pytest

from app.modules.documents.models import EMBEDDING_DIMENSIONS
from app.modules.llm.embeddings import (
    EmbeddingError,
    HashEmbedder,
    VoyageEmbedder,
    create_embedder,
)
from tests.support import make_settings


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


async def test_hash_embedder_returns_unit_vectors_of_the_right_size() -> None:
    vectors = await HashEmbedder().embed_documents(["Net interest income rose.", "", "!!!"])
    for vector in vectors:
        assert len(vector) == EMBEDDING_DIMENSIONS
        assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0, rel_tol=1e-9)


async def test_hash_embedder_ranks_texts_that_share_words_higher() -> None:
    embedder = HashEmbedder()
    query = await embedder.embed_query("What was net interest income?")
    related, unrelated = await embedder.embed_documents(
        ["Net interest income was 12 billion.", "The office moved to a new building."]
    )
    assert _cosine(query, related) > _cosine(query, unrelated) + 0.2


async def test_hash_embedder_is_deterministic() -> None:
    assert await HashEmbedder().embed_query("same text") == await HashEmbedder().embed_query(
        "same text"
    )


def _voyage(handler: Any) -> tuple[VoyageEmbedder, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return VoyageEmbedder("secret-key", "voyage-3.5", client), client


def _ok(request: httpx.Request) -> httpx.Response:
    texts = json.loads(request.content)["input"]
    # Returned out of order on purpose: the client must sort by "index".
    data = [
        {"index": i, "embedding": [float(i)] * EMBEDDING_DIMENSIONS}
        for i in reversed(range(len(texts)))
    ]
    return httpx.Response(200, json={"data": data})


async def test_voyage_batches_documents_and_keeps_their_order() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret-key"
        requests.append(json.loads(request.content))
        return _ok(request)

    embedder, client = _voyage(handler)
    async with client:
        vectors = await embedder.embed_documents([f"text {i}" for i in range(150)])

    assert [len(r["input"]) for r in requests] == [64, 64, 22]
    assert all(r["input_type"] == "document" for r in requests)
    assert all(r["output_dimension"] == EMBEDDING_DIMENSIONS for r in requests)
    assert len(vectors) == 150
    assert [v[0] for v in vectors[:3]] == [0.0, 1.0, 2.0]


async def test_voyage_embeds_queries_as_queries() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content)["input_type"])
        return _ok(request)

    embedder, client = _voyage(handler)
    async with client:
        await embedder.embed_query("what is tier 1 capital?")
    assert seen == ["query"]


async def test_voyage_retries_rate_limits_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr("app.modules.llm.embeddings.asyncio.sleep", fake_sleep)
    statuses = iter([429, 503, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(statuses)
        return _ok(request) if status == 200 else httpx.Response(status)

    embedder, client = _voyage(handler)
    async with client:
        assert len(await embedder.embed_query("q")) == EMBEDDING_DIMENSIONS
    assert delays == [2.0, 4.0]


async def test_voyage_gives_up_after_repeated_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_sleep(seconds: float) -> None:
        pass

    monkeypatch.setattr("app.modules.llm.embeddings.asyncio.sleep", fake_sleep)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("no route")

    embedder, client = _voyage(handler)
    async with client:
        with pytest.raises(EmbeddingError, match="unavailable"):
            await embedder.embed_query("q")
    assert calls == VoyageEmbedder.MAX_ATTEMPTS


async def test_voyage_does_not_retry_a_rejected_request() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"detail": "bad key"})

    embedder, client = _voyage(handler)
    async with client:
        with pytest.raises(EmbeddingError, match="rejected: 401"):
            await embedder.embed_query("q")
    assert calls == 1


async def test_voyage_rejects_vectors_of_the_wrong_size() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]})

    embedder, client = _voyage(handler)
    async with client:
        with pytest.raises(EmbeddingError, match="wrong shape"):
            await embedder.embed_query("q")


async def test_factory_follows_the_settings() -> None:
    async with httpx.AsyncClient() as client:
        assert isinstance(create_embedder(make_settings(), client), HashEmbedder)
        voyage = create_embedder(
            make_settings(embedding_provider="voyage", voyage_api_key="k"), client
        )
        assert isinstance(voyage, VoyageEmbedder)
        assert voyage.model == "voyage-3.5"
