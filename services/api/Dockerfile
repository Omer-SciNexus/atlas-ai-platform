# syntax=docker/dockerfile:1
# Production image for the Atlas API.
#   docker build -t atlas-api services/api
#   docker run --env-file .env -p 8000:8000 atlas-api
# Migrations run as a separate step with the owner role:
#   docker run --env-file .env atlas-api alembic upgrade head
# The ingestion worker is the same image with another command:
#   docker run --env-file .env atlas-api python -m app.worker

FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first, so code changes do not invalidate this layer.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable


FROM python:3.13-slim
# Uploaded files live here until the S3 blob store exists. Mount the same volume into the
# API and the worker containers.
RUN useradd --system --uid 10001 --no-create-home atlas     && mkdir -p /data/blobs && chown atlas /data/blobs
WORKDIR /app
COPY --from=build --chown=root:root /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    ATLAS_LOG_JSON=true     ATLAS_BLOB_DIR=/data/blobs
USER atlas
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
