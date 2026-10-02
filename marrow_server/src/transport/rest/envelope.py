from typing import Any

from fastapi import Request


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


def ok(request: Request, result: Any) -> dict[str, Any]:
    return {"result": result, "request_id": request_id(request)}


def error_body(error_type: str, message: str, req_id: str, details: dict | None = None) -> dict:
    error: dict[str, Any] = {"type": error_type, "message": message}
    if details:
        error["details"] = details
    return {"error": error, "request_id": req_id}
