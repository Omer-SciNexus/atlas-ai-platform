"""Liveness and readiness probes.

``/healthz`` says the process is up (no dependencies, so a database blip does not get the
container killed). ``/readyz`` says it can serve traffic, and the load balancer uses it.
"""

import asyncio
from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import text

router = APIRouter(tags=["health"])

CheckStatus = Literal["ok", "error"]


class HealthOut(BaseModel):
    status: CheckStatus
    version: str


class ReadyOut(BaseModel):
    status: CheckStatus
    checks: dict[str, CheckStatus]


@router.get("/healthz", response_model=HealthOut)
async def healthz(request: Request) -> HealthOut:
    return HealthOut(status="ok", version=request.app.version)


@router.get("/readyz", response_model=ReadyOut)
async def readyz(request: Request, response: Response) -> ReadyOut:
    async def check_db() -> CheckStatus:
        try:
            async with request.app.state.engine.connect() as conn:
                await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=2)
            return "ok"
        except Exception:
            return "error"

    async def check_redis() -> CheckStatus:
        try:
            await asyncio.wait_for(request.app.state.redis.ping(), timeout=2)
            return "ok"
        except Exception:
            return "error"

    db, cache = await asyncio.gather(check_db(), check_redis())
    checks: dict[str, CheckStatus] = {"database": db, "redis": cache}
    ok = all(v == "ok" for v in checks.values())
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyOut(status="ok" if ok else "error", checks=checks)
