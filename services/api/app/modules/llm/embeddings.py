"""Text embeddings behind one small interface.

``VoyageEmbedder`` is the real model. ``HashEmbedder`` needs no key and no network: it is
what local development and the test suite use, and it is refused in staging and production.
Both return unit-length vectors of ``EMBEDDING_DIMENSIONS`` numbers.
"""

import asyncio
import hashlib
import itertools
import math
import re
from collections.abc import Sequence
from typing import Any, Protocol

import httpx
import structlog

from app.core.config import Settings
from app.modules.documents.models import EMBEDDING_DIMENSIONS

log = structlog.get_logger(__name__)


class EmbeddingError(Exception):
    """The embedding provider failed after retries."""


class Embedder(Protocol):
    @property
    def model(self) -> str: ...

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


_WORD = re.compile(r"[a-z0-9]+")


class HashEmbedder:
    """Feature hashing: each word and word pair adds weight at a hashed position.

    Texts that share words get similar vectors, so retrieval works well enough to run the
    whole pipeline offline. It does not understand meaning ("revenue" and "sales" are
    unrelated to it), which is why it is not allowed outside local and test.
    """

    model = "hash-v1"

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        self._dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        words = _WORD.findall(text.lower())
        counts: dict[str, int] = {}
        for feature in [*words, *(f"{a} {b}" for a, b in itertools.pairwise(words))]:
            counts[feature] = counts.get(feature, 0) + 1

        vector = [0.0] * self._dimensions
        for feature, count in counts.items():
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign * (1.0 + math.log(count))

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            # pgvector's cosine distance is undefined for a zero vector.
            vector[0] = 1.0
            return vector
        return [v / norm for v in vector]

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class VoyageEmbedder:
    """Voyage AI embeddings over HTTP.

    Documents and queries are embedded with different ``input_type`` values, as the model
    was trained for: a question and the passage that answers it are not worded alike.
    """

    URL = "https://api.voyageai.com/v1/embeddings"
    BATCH_SIZE = 64
    MAX_ATTEMPTS = 4

    def __init__(self, api_key: str, model: str, client: httpx.AsyncClient) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client

    @property
    def model(self) -> str:
        return self._model

    async def _request(self, texts: Sequence[str], input_type: str) -> list[list[float]]:
        payload = {
            "input": list(texts),
            "model": self._model,
            "input_type": input_type,
            "output_dimension": EMBEDDING_DIMENSIONS,
        }
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                response = await self._client.post(
                    self.URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=30.0,
                )
            except httpx.TransportError as exc:
                failure = type(exc).__name__
            else:
                if response.status_code == 200:
                    return self._vectors(response.json(), expected=len(texts))
                if response.status_code != 429 and response.status_code < 500:
                    # Our request is wrong (bad key, bad model): retrying cannot help.
                    raise EmbeddingError(f"Embedding request rejected: {response.status_code}")
                failure = str(response.status_code)
            log.warning("embeddings.retry", attempt=attempt, failure=failure)
            if attempt < self.MAX_ATTEMPTS:
                await asyncio.sleep(min(2.0**attempt, 20.0))
        raise EmbeddingError("Embedding provider unavailable")

    @staticmethod
    def _vectors(body: Any, *, expected: int) -> list[list[float]]:
        try:
            rows = sorted(body["data"], key=lambda row: row["index"])
            vectors = [[float(v) for v in row["embedding"]] for row in rows]
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingError("Unexpected embedding response") from exc
        if len(vectors) != expected or any(len(v) != EMBEDDING_DIMENSIONS for v in vectors):
            raise EmbeddingError("Embedding response has the wrong shape")
        return vectors

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.BATCH_SIZE):
            vectors.extend(await self._request(texts[start : start + self.BATCH_SIZE], "document"))
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        return (await self._request([text], "query"))[0]


def create_embedder(settings: Settings, client: httpx.AsyncClient) -> Embedder:
    if settings.embedding_provider == "voyage":
        if settings.voyage_api_key is None:  # also checked when settings load
            raise ValueError("ATLAS_VOYAGE_API_KEY is not set")
        return VoyageEmbedder(
            settings.voyage_api_key.get_secret_value(), settings.embedding_model, client
        )
    return HashEmbedder()
