import asyncio
import pytest
from watchdog.events import FileModifiedEvent

from src.watcher.debouncer import AsyncDebouncer
from src.watcher.bridge import SkeletonEventBridge

@pytest.mark.asyncio
async def test_async_debouncer():
    calls = []
    
    async def mock_callback(filepath: str):
        calls.append(filepath)

    loop = asyncio.get_running_loop()
    debouncer = AsyncDebouncer(loop, mock_callback)
    
    # Schedule multiple rapid events (debounce)
    debouncer.schedule("test.cs", delay=0.1)
    await asyncio.sleep(0.02)
    debouncer.schedule("test.cs", delay=0.1)
    await asyncio.sleep(0.02)
    debouncer.schedule("test.cs", delay=0.1)

    # Allow time for delay to finish
    await asyncio.sleep(0.15)
    
    # Callback should only be triggered once
    assert len(calls) == 1
    assert calls[0] == "test.cs"


def test_skeleton_event_bridge():
    class DummyDebouncer:
        def __init__(self):
            self.schedules = []
            
        def schedule(self, filepath: str, delay: float = 7.0):
            self.schedules.append(filepath)

    class DummyLoop:
        def call_soon_threadsafe(self, cb, *args):
            cb(*args) # Just execute immediately for test

    loop = DummyLoop()
    debouncer = DummyDebouncer()
    async def mock_delete(path): pass
    bridge = SkeletonEventBridge(loop, debouncer, extensions=[".cs", ".ts"], delete_callback=mock_delete)
    
    # Valid file
    bridge.on_modified(FileModifiedEvent("valid.cs"))
    assert len(debouncer.schedules) == 1
    assert debouncer.schedules[0] == "valid.cs"
    
    # Invalid extension
    bridge.on_modified(FileModifiedEvent("invalid.txt"))
    assert len(debouncer.schedules) == 1 # Shouldn't trigger

    # Directory
    directory_event = FileModifiedEvent("test_dir")
    directory_event.is_directory = True
    bridge.on_modified(directory_event)
    assert len(debouncer.schedules) == 1 # Shouldn't trigger
