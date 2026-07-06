import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from src.watcher.debouncer import AsyncDebouncer
from watchdog.events import FileSystemEvent, FileSystemEventHandler


class SkeletonEventBridge(FileSystemEventHandler):
    """Bridges threaded watchdog file events into the asyncio main loop."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        debouncer: AsyncDebouncer,
        extensions: list[str],
        delete_callback: Callable[[str], Awaitable[None]],
    ):
        super().__init__()
        self._loop = loop
        self._debouncer = debouncer
        self._extensions = set([ext.lower() for ext in extensions])
        self._delete_callback = delete_callback

    def _process_event(self, event: FileSystemEvent):
        if event.is_directory:
            return

        ext = Path(event.src_path).suffix.lower()
        if ext in self._extensions:
            # Cross the boundary from background thread to main async loop
            self._loop.call_soon_threadsafe(self._debouncer.schedule, event.src_path)

    def _dispatch_delete(self, src_path: str):
        """Dispatches a delete callback from the watchdog thread into the async loop."""
        self._loop.call_soon_threadsafe(asyncio.ensure_future, self._delete_callback(src_path))

    def on_modified(self, event: FileSystemEvent):
        self._process_event(event)

    def on_created(self, event: FileSystemEvent):
        self._process_event(event)

    def on_deleted(self, event: FileSystemEvent):
        if event.is_directory:
            return
        ext = Path(event.src_path).suffix.lower()
        if ext in self._extensions:
            self._dispatch_delete(event.src_path)

    def on_moved(self, event: FileSystemEvent):
        # Delete old path from index
        if not event.is_directory:
            src_ext = Path(event.src_path).suffix.lower()
            if src_ext in self._extensions:
                self._dispatch_delete(event.src_path)
        # Re-index new path via existing debouncer pipeline
        dest_ext = Path(event.dest_path).suffix.lower()
        if not event.is_directory and dest_ext in self._extensions:
            self._loop.call_soon_threadsafe(self._debouncer.schedule, event.dest_path)
