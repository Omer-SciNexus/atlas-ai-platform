"""Documents, ingestion, search and answers end to end: real app, real Postgres + pgvector.

The embedder is the keyless hash embedder and the model is scripted, so these tests are
deterministic and need no API keys. The worker is run in-process, one job at a time.
"""

import asyncio
import json
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app import worker
from app.core.config import Settings
from app.core.db import create_engine, create_sessionmaker
from app.main import create_app
from app.modules.documents.blobs import LocalBlobStore
from app.modules.ingestion.pipeline import IngestionDeps, process_next_job
from app.modules.llm.embeddings import Embedder, EmbeddingError, HashEmbedder
from app.modules.rag.service import NO_SOURCES_ANSWER
from app.modules.retrieval.store import PgVectorStore
from tests.integration.conftest import TENANT_A, TENANT_B, TENANT_EMPTY, DbUrls
from tests.support import FakeIdP, ScriptedAnswerGenerator, make_settings, minimal_pdf

MAX_UPLOAD = 200_000


@dataclass
class Env:
    client: TestClient
    idp: FakeIdP
    settings: Settings
    blob_dir: Path
    generator: ScriptedAnswerGenerator
    db_urls: DbUrls

    def auth(self, tenant: uuid.UUID = TENANT_A, role: str = "editor") -> dict[str, str]:
        token = self.idp.token(sub=f"{role}-{tenant.hex[:6]}", tenant_id=tenant, roles=[role])
        return {"Authorization": f"Bearer {token}"}

    def upload(
        self,
        content: bytes | str,
        filename: str = "notes.md",
        *,
        tenant: uuid.UUID = TENANT_A,
        title: str | None = None,
    ) -> Any:
        data = content.encode() if isinstance(content, str) else content
        return self.client.post(
            "/v1/documents",
            files={"file": (filename, data, "application/octet-stream")},
            data={"title": title} if title else None,
            headers=self.auth(tenant),
        )

    def document(self, document_id: str, tenant: uuid.UUID = TENANT_A) -> dict[str, Any]:
        resp = self.client.get(f"/v1/documents/{document_id}", headers=self.auth(tenant))
        assert resp.status_code == 200, resp.text
        body: dict[str, Any] = resp.json()
        return body

    def run_worker(self, embedder: Embedder | None = None, *, max_jobs: int = 50) -> int:
        """Process queued jobs the way the worker process does. Returns how many ran."""

        async def drain() -> int:
            # Its own engine: the app's engine belongs to the test client's event loop.
            engine = create_engine(self.settings)
            deps = IngestionDeps(
                settings=self.settings,
                sessionmaker=create_sessionmaker(engine),
                blobs=LocalBlobStore(self.blob_dir),
                embedder=embedder or HashEmbedder(),
                vectors=PgVectorStore(),
            )
            try:
                count = 0
                while count < max_jobs and await process_next_job(deps):
                    count += 1
                return count
            finally:
                await engine.dispose()

        return asyncio.run(drain())

    def sql(self, query: str, *args: Any) -> list[asyncpg.Record]:
        """Run SQL as the owner role, to set up or inspect state the API does not expose."""

        async def run() -> list[asyncpg.Record]:
            conn = await asyncpg.connect(self.db_urls.owner_raw)
            try:
                rows: list[asyncpg.Record] = await conn.fetch(query, *args)
                return rows
            finally:
                await conn.close()

        return asyncio.run(run())


@pytest.fixture
def make_env(db_urls: DbUrls, tmp_path: Path) -> Iterator[Callable[..., Env]]:
    clients: list[TestClient] = []

    def build(*, with_model: bool = True, generator: ScriptedAnswerGenerator | None = None) -> Env:
        settings = make_settings(
            database_url=db_urls.app,
            blob_dir=tmp_path / "blobs",
            max_upload_bytes=MAX_UPLOAD,
            worker_poll_seconds=0.05,
            # Small chunks, so a three-section test document becomes three chunks.
            chunk_size_chars=200,
            chunk_overlap_chars=40,
        )
        idp = FakeIdP()
        generator = generator or ScriptedAnswerGenerator()
        app = create_app(settings)
        app.state.token_verifier = idp.verifier(settings)
        app.state.answer_generator = generator if with_model else None
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return Env(client, idp, settings, tmp_path / "blobs", generator, db_urls)

    yield build
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def env(make_env: Callable[..., Env]) -> Env:
    return make_env()


def _unique(word: str = "zircon") -> str:
    """A made-up word no other test's documents contain, so searches are unambiguous."""
    return f"{word}{uuid.uuid4().hex[:10]}"


def _report(token: str) -> str:
    return (
        "# Annual report\n\n"
        "General remarks about the year and the conditions the bank operated in.\n\n"
        f"## Capital\n\nThe {token} ratio was 13.1 percent at year end. "
        "It was above the regulatory minimum.\n\n"
        "## Outlook\n\nManagement expects stable deposits next year.\n"
    )


def _sse(text: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


# ---------- the main flow ----------


def test_upload_ingest_search_and_ask(env: Env) -> None:
    token = _unique()
    created = env.upload(_report(token), "annual_report-2025.md")
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "pending"
    assert body["title"] == "annual report 2025"
    assert body["mime_type"] == "text/markdown"
    document_id = body["id"]

    assert env.run_worker() >= 1
    document = env.document(document_id)
    assert document["status"] == "ready"
    assert document["chunk_count"] >= 1
    assert document["error"] is None

    # Search: the passage with the made-up word comes first, with its section heading.
    found = env.client.post(
        "/v1/search", json={"query": f"What was the {token} ratio?"}, headers=env.auth()
    )
    assert found.status_code == 200, found.text
    top = found.json()["results"][0]
    assert top["document_id"] == document_id
    assert token in top["content"]
    assert top["heading"] == "Capital"
    assert 0 < top["score"] <= 1

    # Ask: the answer cites the uploaded document.
    asked = env.client.post(
        "/v1/ask",
        json={"question": f"What was the {token} ratio?", "stream": False},
        headers=env.auth(role="viewer"),
    )
    assert asked.status_code == 200, asked.text
    answer = asked.json()
    assert answer["answer"] == "According to the documents, this is the answer."
    assert answer["grounded"] is True
    assert answer["model"] == "scripted"
    assert answer["usage"] == {"input_tokens": 100, "output_tokens": 20}
    assert answer["sources"][0]["document_id"] == document_id
    citation = answer["segments"][1]["citations"][0]
    assert citation["document_id"] == document_id
    assert citation["document_title"] == "annual report 2025"
    assert citation["cited_text"] == top["content"][:30]

    # The model saw the retrieved passages, and nothing from the request but the question.
    question, passages = env.generator.calls[-1]
    assert question == f"What was the {token} ratio?"
    assert passages[0].text == top["content"]

    events = env.client.get("/v1/audit-events?limit=200", headers=env.auth(role="admin")).json()
    by_action: dict[str, Any] = {}
    for event in events:  # newest first: keep the newest event of each kind
        if event["resource_id"] in (document_id, None):
            by_action.setdefault(event["action"], event)
    assert by_action["document.uploaded"]["details"]["filename"] == "annual_report-2025.md"
    assert by_action["document.ingested"]["actor_subject"] == "system:ingestion-worker"
    asked_event = by_action["rag.asked"]
    assert top["chunk_id"] in asked_event["details"]["chunk_ids"]
    assert token not in json.dumps(asked_event)  # the question text is not stored


def test_ask_streams_server_sent_events(env: Env) -> None:
    token = _unique()
    document_id = env.upload(_report(token)).json()["id"]
    env.run_worker()

    resp = env.client.post(
        "/v1/ask", json={"question": f"Tell me about {token}"}, headers=env.auth()
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers["x-request-id"]

    events = _sse(resp.text)
    assert [name for name, _ in events] == [
        "sources", "delta", "delta", "citation", "delta", "done",
    ]  # fmt: skip
    assert events[0][1]["sources"][0]["document_id"] == document_id
    assert events[3][1]["segment"] == 1
    assert events[3][1]["document_id"] == document_id
    assert events[-1][1]["grounded"] is True


def test_pdf_pages_are_kept_for_citations(env: Env) -> None:
    token = _unique("quartz")
    pdf = minimal_pdf(["Cover page of the filing.", f"The {token} reserve was 2.4 billion."])
    document_id = env.upload(pdf, "filing.pdf").json()["id"]
    env.run_worker()
    assert env.document(document_id)["status"] == "ready"

    results = env.client.post(
        "/v1/search", json={"query": f"{token} reserve", "top_k": 1}, headers=env.auth()
    ).json()["results"]
    assert len(results) == 1
    assert token in results[0]["content"]
    assert results[0]["page"] in (1, 2)  # both short pages fit in one chunk, labeled by its start


# ---------- tenant isolation ----------


def test_documents_and_search_are_isolated_between_tenants(env: Env) -> None:
    token = _unique()
    document_id = env.upload(_report(token), tenant=TENANT_A).json()["id"]
    env.upload(f"Globex has its own notes. {_unique('opal')} is mentioned here.", tenant=TENANT_B)
    env.run_worker()

    other = env.auth(TENANT_B, role="owner")
    assert env.client.get(f"/v1/documents/{document_id}", headers=other).status_code == 404
    assert env.client.delete(f"/v1/documents/{document_id}", headers=other).status_code == 404
    listed = env.client.get("/v1/documents?limit=100", headers=other).json()["items"]
    assert document_id not in [d["id"] for d in listed]

    # The other tenant searches for the exact made-up word and still gets none of it.
    results = env.client.post(
        "/v1/search", json={"query": token, "top_k": 50}, headers=other
    ).json()["results"]
    assert results  # it has its own document
    assert all(r["document_id"] != document_id for r in results)
    assert all(token not in r["content"] for r in results)

    assert env.document(document_id)["status"] == "ready"  # untouched by the 404 delete


def test_tenant_without_documents_gets_no_answer_and_no_model_call(env: Env) -> None:
    env.upload(_report(_unique()))
    env.run_worker()

    resp = env.client.post(
        "/v1/ask",
        json={"question": "What was the capital ratio?", "stream": False},
        headers=env.auth(TENANT_EMPTY),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["answer"] == NO_SOURCES_ANSWER
    assert body["sources"] == []
    assert body["grounded"] is False
    assert env.generator.calls == []


# ---------- uploads ----------


def test_duplicate_upload_returns_the_existing_document(env: Env) -> None:
    content = _report(_unique())
    first = env.upload(content)
    second = env.upload(content, "renamed.md")
    assert (first.status_code, second.status_code) == (201, 200)
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["filename"] == "notes.md"

    # The same bytes in another tenant are that tenant's own document.
    other = env.upload(content, tenant=TENANT_B)
    assert other.status_code == 201
    assert other.json()["id"] != first.json()["id"]


def test_custom_title_and_unsafe_filename(env: Env) -> None:
    resp = env.upload(_report(_unique()), "..\\..\\evil/../report.md", title="  Q3 Board Pack ")
    assert resp.status_code == 201
    assert resp.json()["title"] == "Q3 Board Pack"
    assert resp.json()["filename"] == "report.md"


@pytest.mark.parametrize(
    ("filename", "content", "status", "detail"),
    [
        ("tool.exe", b"MZ\x90\x00", 415, "Unsupported file type"),
        ("renamed.pdf", b"just text, not a pdf", 415, "does not match"),
        ("blank.txt", b"  \n\n  ", 422, "File is empty"),
        ("big.txt", b"a" * (MAX_UPLOAD + 1), 413, "larger than"),
    ],
)
def test_bad_uploads_are_rejected(
    env: Env, filename: str, content: bytes, status: int, detail: str
) -> None:
    resp = env.upload(content, filename)
    assert resp.status_code == status
    assert detail in resp.json()["detail"]
    assert resp.headers["content-type"].startswith("application/problem+json")


def test_list_is_paged_newest_first(env: Env) -> None:
    tenant_docs = [env.upload(_report(_unique())).json()["id"] for _ in range(3)]

    seen: list[str] = []
    cursor: str | None = None
    for _ in range(200):
        params = {"limit": 2} | ({"cursor": cursor} if cursor else {})
        page = env.client.get("/v1/documents", params=params, headers=env.auth()).json()
        assert len(page["items"]) <= 2
        seen.extend(d["id"] for d in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert len(seen) == len(set(seen))  # no row twice
    assert seen[:3] == tenant_docs[::-1]  # newest first
    bad = env.client.get("/v1/documents?cursor=garbage", headers=env.auth())
    assert bad.status_code == 422


def test_delete_removes_the_document_its_chunks_and_its_file(env: Env) -> None:
    token = _unique()
    document_id = env.upload(_report(token)).json()["id"]
    env.run_worker()
    blob = env.blob_dir / str(TENANT_A) / document_id
    assert blob.exists()

    viewer = env.client.delete(f"/v1/documents/{document_id}", headers=env.auth(role="viewer"))
    assert viewer.status_code == 403
    deleted = env.client.delete(f"/v1/documents/{document_id}", headers=env.auth())
    assert deleted.status_code == 204

    assert env.client.get(f"/v1/documents/{document_id}", headers=env.auth()).status_code == 404
    assert not blob.exists()
    doc_uuid = uuid.UUID(document_id)
    assert env.sql("SELECT 1 FROM document_chunks WHERE document_id = $1", doc_uuid) == []
    assert env.sql("SELECT 1 FROM ingestion_jobs WHERE document_id = $1", doc_uuid) == []
    results = env.client.post("/v1/search", json={"query": token}, headers=env.auth()).json()
    assert all(r["document_id"] != document_id for r in results["results"])

    events = env.client.get("/v1/audit-events?limit=50", headers=env.auth(role="admin")).json()
    assert any(
        e["action"] == "document.deleted" and e["resource_id"] == document_id for e in events
    )


# ---------- ingestion failures ----------


def test_unreadable_file_fails_with_a_message_and_is_not_retried(env: Env) -> None:
    document_id = env.upload(b"%PDF-1.4\nnot really a pdf", "broken.pdf").json()["id"]
    env.run_worker()

    document = env.document(document_id)
    assert document["status"] == "failed"
    assert document["error"]
    assert document["chunk_count"] == 0
    job = env.sql(
        "SELECT status, attempts FROM ingestion_jobs WHERE document_id = $1",
        uuid.UUID(document_id),
    )[0]
    assert (job["status"], job["attempts"]) == ("failed", 1)

    events = env.client.get("/v1/audit-events?limit=50", headers=env.auth(role="admin")).json()
    assert any(
        e["action"] == "document.ingestion_failed" and e["resource_id"] == document_id
        for e in events
    )


class _FailingEmbedder:
    model = "failing"

    def __init__(self, failures: int) -> None:
        self.remaining = failures

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if self.remaining > 0:
            self.remaining -= 1
            raise EmbeddingError("Embedding provider unavailable")
        return await HashEmbedder().embed_documents(texts)

    async def embed_query(self, text: str) -> list[float]:
        return await HashEmbedder().embed_query(text)


def _make_due(env: Env, document_id: str) -> None:
    env.sql(
        "UPDATE ingestion_jobs SET run_after = now() WHERE document_id = $1",
        uuid.UUID(document_id),
    )


def test_a_temporary_embedding_outage_is_retried_with_a_delay(env: Env) -> None:
    env.run_worker()  # clear jobs left by other tests
    document_id = env.upload(_report(_unique())).json()["id"]
    embedder = _FailingEmbedder(failures=1)

    assert env.run_worker(embedder) == 1
    job = env.sql(
        "SELECT status, attempts, last_error, run_after > now() AS delayed "
        "FROM ingestion_jobs WHERE document_id = $1",
        uuid.UUID(document_id),
    )[0]
    assert dict(job) == {
        "status": "queued", "attempts": 1, "last_error": "EmbeddingError", "delayed": True,
    }  # fmt: skip
    assert env.document(document_id)["status"] == "processing"
    assert env.run_worker(embedder) == 0  # not due yet

    _make_due(env, document_id)
    assert env.run_worker(embedder) == 1
    assert env.document(document_id)["status"] == "ready"


def test_ingestion_gives_up_after_the_maximum_attempts(env: Env) -> None:
    env.run_worker()
    document_id = env.upload(_report(_unique())).json()["id"]
    embedder = _FailingEmbedder(failures=99)

    for _ in range(env.settings.ingestion_max_attempts):
        _make_due(env, document_id)
        assert env.run_worker(embedder) == 1

    document = env.document(document_id)
    assert document["status"] == "failed"
    assert document["error"] == "Ingestion failed after 3 attempts"
    _make_due(env, document_id)
    assert env.run_worker(embedder) == 0  # a failed job is never picked up again


def test_a_job_left_by_a_dead_worker_is_taken_over(env: Env) -> None:
    env.run_worker()
    document_id = env.upload(_report(_unique())).json()["id"]
    env.sql(
        "UPDATE ingestion_jobs SET status = 'running', attempts = 1, "
        "locked_at = now() - interval '1 hour' WHERE document_id = $1",
        uuid.UUID(document_id),
    )
    assert env.run_worker() == 1
    assert env.document(document_id)["status"] == "ready"


def test_a_document_deleted_during_ingestion_is_skipped(env: Env) -> None:
    env.run_worker()
    document_id = env.upload(_report(_unique())).json()["id"]
    assert env.client.delete(f"/v1/documents/{document_id}", headers=env.auth()).status_code == 204
    assert env.run_worker() == 0  # its job went with it
