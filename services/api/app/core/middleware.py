"""Pure-ASGI request context middleware.

Written as raw ASGI (not BaseHTTPMiddleware) so it adds no overhead and works with the
streaming (SSE) responses the chat endpoints will use.

It also turns unhandled exceptions into the problem+json 500. That cannot live in an app-level
``Exception`` handler: Starlette runs those in ``ServerErrorMiddleware``, which sits *outside*
this middleware, so the response would miss the ``X-Request-ID`` header and the error log
would miss the request context.
"""

import re
import time
import uuid

import structlog
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import problem

REQUEST_ID_HEADER = b"x-request-id"
# Accept a caller's request id only if it is short and safe to log.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

log = structlog.get_logger("atlas.http")


def _incoming_request_id(scope: Scope) -> str:
    for name, value in scope.get("headers", []):
        if name == REQUEST_ID_HEADER:
            candidate = bytes(value).decode("latin-1")
            if _SAFE_REQUEST_ID.match(candidate):
                return candidate
            break
    return uuid.uuid4().hex


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        scope.setdefault("state", {})["request_id"] = request_id

        status_code = 500
        response_started = False
        started = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER, request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            # Logged here, while request_id / tenant_id are still bound to the context.
            log.exception("unhandled_error", path=scope.get("path", ""))
            if response_started:
                raise  # Too late to send an error response; let the server drop the connection.
            status_code = 500
            response = problem(Request(scope), 500, "Internal server error")
            await response(scope, receive, send_with_request_id)
        finally:
            path = scope.get("path", "")
            if path not in ("/healthz", "/readyz"):
                log.info(
                    "http.request",
                    method=scope.get("method"),
                    path=path,
                    status=status_code,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                )
            structlog.contextvars.clear_contextvars()
