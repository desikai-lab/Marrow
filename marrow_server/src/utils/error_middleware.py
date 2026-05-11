"""
Centralized error handling decorator for MCP tools.

Usage in mcp_core.py:
    @mcp.tool()
    @mcp_error_handler          # <-- must be BELOW @mcp.tool()
    def some_tool(...):
        ...
"""
import asyncio
import functools
import inspect
import logging
from typing import Any, Callable

from tools.utils.security import sanitize_error_message
from utils.exceptions import BaseBacklogError

logger = logging.getLogger(__name__)


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
                return _handle_domain_error(e, func.__name__)
            except Exception as e:
                return _handle_system_error(e, func.__name__)
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except BaseBacklogError as e:
                return _handle_domain_error(e, func.__name__)
            except Exception as e:
                return _handle_system_error(e, func.__name__)
        return sync_wrapper


def _handle_domain_error(e: BaseBacklogError, func_name: str) -> dict:
    logger.warning(
        "[MCP][DomainError] %s in %s: %s",
        type(e).__name__, func_name, e.message
    )
    response = {
        "status": "error",
        "error_type": type(e).__name__,
        "message": e.message,
    }
    if e.details:
        response["details"] = e.details
    return response


def _handle_system_error(e: Exception, func_name: str) -> dict:
    logger.error(
        "[MCP][SystemError] %s in %s: %s",
        type(e).__name__, func_name, e,
        exc_info=True
    )
    return {
        "status": "error",
        "error_type": "SystemError",
        "message": f"Internal error: {sanitize_error_message(str(e))}",
    }
