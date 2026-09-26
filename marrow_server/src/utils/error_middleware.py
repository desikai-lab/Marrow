"""
Centralized error handling decorator for MCP tools.

Usage in mcp_core.py:
    @mcp.tool()
    @mcp_error_handler          # <-- must be BELOW @mcp.tool()
    def some_tool(...):
        ...
"""

import functools
import inspect
import logging
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from common.path_resolver import get_artifacts_path
from config import EXTERNAL_DEBUG
from tools.utils.security import sanitize_error_message

from utils.exceptions import BaseBacklogError

logger = logging.getLogger(__name__)


class DebugArtifactLogHandler(logging.Handler):
    """Writes a debug record to <project>/artifacts/Debug.log when the record
    carries a 'project' and 'debug_traceback' extra field. Never raises —
    any failure is swallowed via self.handleError (standard logging contract),
    which itself only ever writes to stderr and never propagates.
    Deliberately does NOT read record.exc_info / use the record's own
    traceback rendering: only the explicit 'debug_traceback' extra is used,
    so attaching this handler cannot change what any *other* handler on this
    logger (e.g. an existing console handler) prints for the same log call.
    """

    def emit(self, record: logging.LogRecord) -> None:
        project = getattr(record, "project", None)
        debug_tb = getattr(record, "debug_traceback", None)
        if not isinstance(project, str) or not project or not debug_tb:
            return
        try:
            entry_path = get_artifacts_path(project, "Debug.log")
            timestamp = datetime.now(UTC).isoformat()
            entry = f"\n--- {timestamp} | {record.funcName} ---\n{debug_tb}\n"
            existing = entry_path.read() if entry_path.exists() else ""
            entry_path.write(existing + entry)
        except Exception:
            self.handleError(record)


if EXTERNAL_DEBUG:
    logger.addHandler(DebugArtifactLogHandler())
    # Attached to THIS module's logger only — never logging.getLogger() root —
    # so it can only ever fire for the two call sites below, matching Option A's
    # exact scope. Existing handlers/propagation on this logger are untouched.


def mcp_error_handler(func: Callable) -> Callable:
    """
    Decorator that centralises error handling for every MCP tool.
    Supports both synchronous and asynchronous tool functions.

    Behaviour:
    - If the wrapped function returns normally  → result is passed through unchanged.
    - If a BaseBacklogError (domain error) is raised → returns a structured
      error dict with 'error_type' equal to the concrete exception class name.
    - If any other Exception is raised (system error) → returns a structured
      error dict with 'error_type': 'SystemError' and a sanitised message.
    """
    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except BaseBacklogError as e:
                return _handle_domain_error(e, func.__name__, kwargs.get("project"))
            except Exception as e:
                return _handle_system_error(e, func.__name__, kwargs.get("project"))

        return async_wrapper
    else:

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except BaseBacklogError as e:
                return _handle_domain_error(e, func.__name__, kwargs.get("project"))
            except Exception as e:
                return _handle_system_error(e, func.__name__, kwargs.get("project"))

        return sync_wrapper


def _handle_domain_error(e: BaseBacklogError, func_name: str, project: Any = None) -> dict:
    logger.warning(
        "[MCP][DomainError] %s in %s: %s",
        type(e).__name__,
        func_name,
        e.message,
        extra={"project": project, "debug_traceback": traceback.format_exc()}
        if EXTERNAL_DEBUG
        else None,
    )
    response = {
        "status": "error",
        "error_type": type(e).__name__,
        "message": e.message,
    }
    if e.details:
        response["details"] = e.details
    return response


def _handle_system_error(e: Exception, func_name: str, project: Any = None) -> dict:
    logger.error(
        "[MCP][SystemError] %s in %s: %s",
        type(e).__name__,
        func_name,
        e,
        exc_info=True,
        extra={"project": project, "debug_traceback": traceback.format_exc()}
        if EXTERNAL_DEBUG
        else None,
    )
    return {
        "status": "error",
        "error_type": "SystemError",
        "message": f"Internal error: {sanitize_error_message(str(e))}",
    }
