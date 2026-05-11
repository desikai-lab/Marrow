import asyncio
import json
import logging
import time
from functools import wraps


def get_perf_logger() -> logging.Logger:
    return logging.getLogger("performance_metrics")

def track_time(layer: str, operation: str = None):
    def decorator(func):
        op_name = operation or func.__name__
        
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                extra = kwargs.pop("_perf_extra", {})
                start = time.perf_counter()
                try:
                    return await func(*args, **kwargs)
                finally:
                    duration_ms = (time.perf_counter() - start) * 1000
                    metric = {
                        "layer": layer,
                        "operation": op_name,
                        "duration_ms": round(duration_ms, 2),
                        **extra
                    }
                    get_perf_logger().info(f"[PERF] {json.dumps(metric)}")
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                extra = kwargs.pop("_perf_extra", {})
                start = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    duration_ms = (time.perf_counter() - start) * 1000
                    metric = {
                        "layer": layer,
                        "operation": op_name,
                        "duration_ms": round(duration_ms, 2),
                        **extra
                    }
                    get_perf_logger().info(f"[PERF] {json.dumps(metric)}")
            return sync_wrapper

    return decorator
