"""Pure-ASGI middlewares for the REST app (no BaseHTTPMiddleware: bodies stream untouched)."""

import asyncio
import json
import logging
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from transport.rest.envelope import error_body
from transport.rest.errors import system_error_body

logger = logging.getLogger("marrow.rest")


class _BodyTooLarge(Exception):
    pass


def _state(scope: Scope) -> dict:
    return scope.setdefault("state", {})


def _rid(scope: Scope) -> str:
    return _state(scope).get("request_id", "-")


async def _send_json(send: Send, status: int, body: dict, headers: dict | None = None) -> None:
    payload = json.dumps(body).encode("utf-8")
    raw = [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]
    raw += [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    await send({"type": "http.response.start", "status": status, "headers": raw})
    await send({"type": "http.response.body", "body": payload})


def _log_access(scope: Scope, status: int, started: float) -> None:
    state = _state(scope)
    logger.info(
        "[REST] %s %s %s %.1fms label=%s req=%s",
        scope["method"],
        scope.get("path", "-"),
        status,
        (time.perf_counter() - started) * 1000,
        state.get("key_label", "-"),
        state.get("request_id", "-"),
    )


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        rid = uuid.uuid4().hex[:8]
        _state(scope)["request_id"] = rid
        started = time.perf_counter()
        seen = {"status": 500, "started": False}

        async def tracking_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                seen["status"], seen["started"] = message["status"], True
                message["headers"] = [*message.get("headers", []), (b"x-request-id", rid.encode())]
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            logger.error("[REST] unhandled %s", type(exc).__name__, exc_info=True)
            if not seen["started"]:
                await _send_json(tracking_send, 500, system_error_body(exc, rid))
        finally:
            _log_access(scope, seen["status"], started)


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        length = dict(scope["headers"]).get(b"content-length", b"")
        if length.isdigit() and int(length) > self.max_bytes:
            await self._reject(scope, send)
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await self._reject(scope, send)

    async def _reject(self, scope: Scope, send: Send) -> None:
        message = f"Request body exceeds {self.max_bytes} bytes."
        await _send_json(send, 413, error_body("PayloadTooLarge", message, _rid(scope)))


class ConcurrencyLimitMiddleware:
    def __init__(self, app: ASGIApp, limit: int) -> None:
        self.app = app
        self._sem = asyncio.Semaphore(limit)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if self._sem.locked():
            body = error_body("ServerBusy", "Too many concurrent requests.", _rid(scope))
            await _send_json(send, 503, body, {"Retry-After": "1"})
            return
        async with self._sem:
            await self.app(scope, receive, send)
