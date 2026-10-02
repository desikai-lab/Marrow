from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from tools.utils.security import sanitize_error_message
from utils.exceptions import (
    ArtifactNotFoundError,
    BaseBacklogError,
    DomainProtectionError,
    InvalidPathError,
    ProjectNotFoundError,
    SourceAccessDisabledError,
    SourceFileError,
    StorageTimeoutError,
    TaskNotFoundError,
    ValidationError,
)

from transport.rest.envelope import error_body, request_id


class RestAuthError(Exception):
    """Uniform authentication failure (ADR-0053 section 8)."""


_DOMAIN_STATUS = (
    (InvalidPathError, 400),
    (ProjectNotFoundError, 404),
    (TaskNotFoundError, 404),
    (ArtifactNotFoundError, 404),
    (DomainProtectionError, 409),
    (SourceAccessDisabledError, 409),
    (ValidationError, 422),
    (SourceFileError, 422),
    (StorageTimeoutError, 503),
)
_HTTP_TYPES = {404: "NotFound", 405: "MethodNotAllowed", 413: "PayloadTooLarge"}


def status_for(exc: BaseBacklogError) -> int:
    for cls, code in _DOMAIN_STATUS:
        if isinstance(exc, cls):
            return code
    return 400


def system_error_body(exc: Exception, req_id: str) -> dict:
    message = f"Internal error: {sanitize_error_message(str(exc))}"
    return error_body("SystemError", message, req_id)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RestAuthError)
    async def _auth(request: Request, exc: RestAuthError):
        body = error_body("Unauthorized", "Invalid or missing credentials.", request_id(request))
        return JSONResponse(body, status_code=401, headers={"WWW-Authenticate": "Bearer"})

    @app.exception_handler(BaseBacklogError)
    async def _domain(request: Request, exc: BaseBacklogError):
        code = status_for(exc)
        headers = {"Retry-After": "1"} if code == 503 else None
        body = error_body(type(exc).__name__, exc.message, request_id(request), exc.details)
        return JSONResponse(body, status_code=code, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        errors = [
            {"loc": list(e.get("loc", ())), "msg": e.get("msg", ""), "type": e.get("type", "")}
            for e in exc.errors()
        ]
        body = error_body(
            "ValidationError", "Request validation failed.", request_id(request), {"errors": errors}
        )
        return JSONResponse(body, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        kind = _HTTP_TYPES.get(exc.status_code, "HttpError")
        body = error_body(kind, str(exc.detail), request_id(request))
        return JSONResponse(
            body, status_code=exc.status_code, headers=getattr(exc, "headers", None)
        )
