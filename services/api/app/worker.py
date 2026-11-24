"""Ingestion worker: a separate process that turns uploaded files into searchable chunks.

    uv run python -m app.worker

It is separate from the API so that parsing a 300-page PDF never slows down a chat request,
and so the two can be scaled on their own. Run as many copies as needed; jobs are claimed
with ``FOR UPDATE SKIP LOCKED``, so two workers never take the same one.
"""

import asyncio
import contextlib
import signal

import httpx
import structlog

from app.core.config import Settings, get_settings
from app.core.db import create_engine, create_sessionmaker
from app.core.logging import configure_logging
from app.modules.documents.blobs import LocalBlobStore
from app.modules.ingestion.pipeline import IngestionDeps, process_next_job
from app.modules.llm.embeddings import create_embedder
from app.modules.retrieval.store import PgVectorStore

log = structlog.get_logger("atlas.worker")


async def _loop(deps: IngestionDeps, stop: asyncio.Event, name: str) -> None:
    while not stop.is_set():
        try:
            worked = await process_next_job(deps)
        except Exception:
            # For example the database is down. Log, wait, try again; never exit the loop.
            log.exception("worker.loop_error", worker=name)
            worked = False
        if not worked:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=deps.settings.worker_poll_seconds)


async def run(settings: Settings, stop: asyncio.Event | None = None) -> None:
    stop = stop or asyncio.Event()
    engine = create_engine(settings)
    async with httpx.AsyncClient() as http:
        deps = IngestionDeps(
            settings=settings,
            sessionmaker=create_sessionmaker(engine),
            blobs=LocalBlobStore(settings.blob_dir),
            embedder=create_embedder(settings, http),
            vectors=PgVectorStore(),
        )
        log.info(
            "worker.started",
            concurrency=settings.worker_concurrency,
            embedding_model=deps.embedder.model,
        )
        try:
            async with asyncio.TaskGroup() as group:
                for index in range(settings.worker_concurrency):
                    group.create_task(_loop(deps, stop, f"w{index}"))
        finally:
            # A job that was running when we stop stays "running" and is taken over by
            # another worker once its lock expires.
            await engine.dispose()
            log.info("worker.stopped")


def main() -> None:
    settings = get_settings()
    configure_logging(settings)

    async def _main() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            # Not available on Windows, where Ctrl+C raises KeyboardInterrupt instead.
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, stop.set)
        await run(settings, stop)

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_main())


if __name__ == "__main__":
    main()
