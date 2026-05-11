from unittest.mock import AsyncMock, MagicMock

from src.watcher.bridge import SkeletonEventBridge


def make_bridge(delete_cb=None):
    loop = MagicMock()
    debouncer = MagicMock()
    delete_cb = delete_cb or AsyncMock()
    bridge = SkeletonEventBridge(loop, debouncer, [".py"], delete_callback=delete_cb)
    return bridge, loop, debouncer, delete_cb


def test_on_deleted_fires_callback():
    bridge, loop, _, cb = make_bridge()
    event = MagicMock(is_directory=False, src_path="/repo/foo.py")
    bridge.on_deleted(event)
    loop.call_soon_threadsafe.assert_called_once()


def test_on_deleted_ignores_directory():
    bridge, loop, _, _ = make_bridge()
    event = MagicMock(is_directory=True, src_path="/repo/somedir")
    bridge.on_deleted(event)
    loop.call_soon_threadsafe.assert_not_called()


def test_on_deleted_ignores_wrong_extension():
    bridge, loop, _, _ = make_bridge()
    event = MagicMock(is_directory=False, src_path="/repo/image.png")
    bridge.on_deleted(event)
    loop.call_soon_threadsafe.assert_not_called()


def test_on_moved_fires_delete_and_schedule():
    bridge, loop, debouncer, cb = make_bridge()
    # Create a mock awaitable for the callback
    mock_awaitable = MagicMock()
    cb.return_value = mock_awaitable

    event = MagicMock(is_directory=False, src_path="/repo/old.py", dest_path="/repo/new.py")
    bridge.on_moved(event)

    # Print calls for debugging
    print(f"DEBUG: call_soon_threadsafe calls: {loop.call_soon_threadsafe.call_args_list}")

    # Verify that call_soon_threadsafe was called twice (delete + schedule)
    assert loop.call_soon_threadsafe.call_count == 2

    # Verify the callback was called once
    cb.assert_called_once_with("/repo/old.py")

    # One of the calls to call_soon_threadsafe should have debouncer.schedule as first arg
    schedule_calls = [
        c for c in loop.call_soon_threadsafe.call_args_list if c.args[0] == debouncer.schedule
    ]
    assert len(schedule_calls) == 1, f"Expected 1 schedule call, got {len(schedule_calls)}"
    assert schedule_calls[0].args[1] == "/repo/new.py"
