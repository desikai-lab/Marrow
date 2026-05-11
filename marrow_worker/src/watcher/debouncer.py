import asyncio
from collections.abc import Awaitable, Callable


class AsyncDebouncer:
    """Delays execution of a file processing callback until a stable period clears."""

    def __init__(
        self, loop: asyncio.AbstractEventLoop, on_stable_callback: Callable[[str], Awaitable[None]]
    ):
        self._loop = loop
        self._callback = on_stable_callback
        self._tasks: dict[str, asyncio.Task] = {}

    def schedule(self, filepath: str, delay: float = 7.0) -> None:
        """Schedules or resets the timer for a file."""
        if filepath in self._tasks:
            self._tasks[filepath].cancel()

        async def _wait_and_trigger():
            try:
                await asyncio.sleep(delay)
                # Remove self from tracking before executing callback
                if filepath in self._tasks:
                    del self._tasks[filepath]

                await self._callback(filepath)
            except asyncio.CancelledError:
                # Cancelled due to a new schedule call (debounce successful)
                pass

        self._tasks[filepath] = self._loop.create_task(_wait_and_trigger())
