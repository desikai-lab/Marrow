import json
import logging
import os
import time
import uuid

from config import SECRET_TOKEN
from fastapi import Request
from starlette.responses import JSONResponse
from utils.metrics import get_perf_logger

logger = logging.getLogger("marrow.transport.middleware")


def debug_log(msg: str):
    """Logs debug information."""
    logger.debug(msg)


class DebugLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers_dict = {
                k.decode("utf-8"): v.decode("utf-8") for k, v in scope.get("headers", [])
            }
            logger.debug(f"[HTTP IN] {scope['method']} {scope.get('path', '')}")
            logger.debug(f"[HTTP HEADERS] {headers_dict}")
            query = scope.get("query_string", b"").decode()
            logger.debug(f"[HTTP QUERY] {query}")

        await self.app(scope, receive, send)


class TimingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ["http", "websocket"]:
            return await self.app(scope, receive, send)

        request_id = uuid.uuid4().hex[:8]  # short 8-char hex
        scope["request_id"] = request_id  # available to all downstream handlers

        start = time.perf_counter()
        try:
            await self.app(scope, receive, send)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            path = scope.get("path", "unknown")
            method = scope.get("method", "unknown")
            metric = {
                "layer": "transport",
                "method": method,
                "route": path,
                "duration_ms": round(duration_ms, 2),
                "request_id": request_id,
            }
            get_perf_logger().info(f"[PERF] {json.dumps(metric)}")


class FixHostHeaderMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            headers = list(scope.get("headers", []))

            # sessionId -> session_id mapping for Claude compliance (if needed)
            query_string = scope.get("query_string", b"").decode(errors="ignore")
            if "sessionId=" in query_string and "session_id=" not in query_string:
                new_query = query_string.replace("sessionId=", "session_id=")
                scope["query_string"] = new_query.encode()

            # Strip accept-encoding to prevent SSE buffering by GZip Middlewares
            if scope.get("path") in ("/mcp", "/sse"):
                headers = [(k, v) for k, v in headers if k.lower() != b"accept-encoding"]
                scope["headers"] = headers

        await self.app(scope, receive, send)


class SSEHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def custom_send(message):
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])

                is_sse = False
                for name, value in headers:
                    if name.lower() == b"content-type" and b"text/event-stream" in value.lower():
                        is_sse = True
                        break

                if is_sse:
                    headers = [
                        (k, v)
                        for k, v in headers
                        if k.lower()
                        not in (b"x-accel-buffering", b"cache-control", b"mcp-protocol-version")
                    ]
                    headers.append((b"x-accel-buffering", b"no"))
                    headers.append((b"cache-control", b"no-cache"))
                    headers.append((b"mcp-protocol-version", b"2024-11-05"))
                    message["headers"] = headers
                    debug_log(">>> [SSE DEBUG] Final SSE headers set")

            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if b"event: endpoint" in body:
                    logger.debug(f"[SSE OUT ENDPOINT] {body.decode('utf-8', errors='ignore')}")

                if body and b"event: endpoint" in body and b"data: /messages" in body:
                    base_url_env = os.getenv("BASE_URL", "").rstrip("/")
                    if base_url_env:
                        base_url = base_url_env.encode()
                    else:
                        host = b"localhost:8000"
                        proto = b"http"
                        for k, v in scope.get("headers", []):
                            if k.lower() == b"x-forwarded-host":
                                host = v
                            elif k.lower() == b"host" and host == b"localhost:8000":
                                host = v
                            elif k.lower() == b"x-forwarded-proto":
                                proto = v
                        base_url = proto.rstrip(b":") + b"://" + host
                    body = body.replace(b"data: /messages", b"data: " + base_url + b"/messages")
                    message["body"] = body
                    debug_log(
                        f">>> [SSE REWRITE] Forced absolute URL: {body.decode('utf-8', 'ignore').strip()}"
                    )
                elif body:
                    debug_log(f">>> [SSE DEBUG] Body chunk. Raw snippet: {repr(body)[:120]}")

            await send(message)

        await self.app(scope, receive, custom_send)


class TokenAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)

        request = Request(scope)
        path = request.url.path

        # DEBUG LOGGING (B53)
        auth_header = request.headers.get("Authorization", "")
        token_param = request.query_params.get("token", "")
        debug_log(
            f">>> [AUTH DEBUG] Path: {path}, Method: {request.method if 'method' in scope else '?'}"
        )

        SKIP_PATHS = {
            "/.well-known",
            "/authorize",
            "/token",
            "/register",
            "/authorize_confirm",
            "/health",
            "/userinfo",
        }
        is_protected_path = path.rstrip("/") in ("/messages", "/sse", "/mcp", "/api/vectorize")

        if any(path.startswith(p) for p in SKIP_PATHS) or not is_protected_path:
            debug_log(f">>> [AUTH SKIP] Allowed by skip policy: {path}")
            return await self.app(scope, receive, send)

        debug_log(f">>> [AUTH CHECK] Path is protected ({path}). Validating token...")
        if request.method == "OPTIONS":
            return await self.app(scope, receive, send)

        token = (
            auth_header[7:].strip()
            if auth_header.lower().startswith("bearer ")
            else auth_header.strip()
        )
        if not token:
            token = token_param

        if token != SECRET_TOKEN:
            # Short log (always) + detailed log (verbose)
            logger.warning(f"!!! [AUTH FAILED] Path: {path}")
            debug_log(
                f"    ProvidedToken: {repr(token)[:20]}..., Expected: {repr(SECRET_TOKEN)[:20]}..."
            )
            forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get(
                "x-original-host"
            )
            forwarded_proto = request.headers.get("x-forwarded-proto", "https")
            base_url_env = os.getenv("BASE_URL", "").rstrip("/")
            if forwarded_host:
                base_url = f"{forwarded_proto}://{forwarded_host}"
            elif base_url_env:
                base_url = base_url_env
            else:
                base_url = str(request.base_url).rstrip("/")

            path_cleaned = path.strip("/")
            metadata_url = f"{base_url}/.well-known/oauth-protected-resource/{path_cleaned}"

            response = JSONResponse({"error": "invalid_token"}, status_code=401)
            response.headers["WWW-Authenticate"] = (
                f'Bearer realm="mcp", resource_metadata="{metadata_url}"'
            )
            response.headers["Access-Control-Expose-Headers"] = "WWW-Authenticate"
            response.headers["Access-Control-Allow-Origin"] = "*"
            return await response(scope, receive, send)

        debug_log(f">>> [AUTH SUCCESS] {path}")

        return await self.app(scope, receive, send)
