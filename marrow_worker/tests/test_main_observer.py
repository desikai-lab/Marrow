import asyncio
from unittest.mock import MagicMock, AsyncMock, patch


def test_serve_uses_polling_observer():
    """
    serve() must instantiate PollingObserver, not Observer.
    inotify-based Observer does not fire on Docker bind-mounted volumes.
    """
    mock_outbox_instance = MagicMock()
    mock_outbox_instance.setup = AsyncMock()
    mock_outbox_instance.flush_pending_batched = AsyncMock()
    mock_outbox_instance.background_flush_loop = AsyncMock()
    mock_outbox_instance.close = AsyncMock()

    mock_client_instance = MagicMock()
    mock_client_instance.close = AsyncMock()
    mock_client_instance._make_deliver_fn = MagicMock()

    with patch("main.PollingObserver") as mock_polling, \
         patch("main.MCPClient", return_value=mock_client_instance), \
         patch("main.WorkerOutbox", return_value=mock_outbox_instance), \
         patch("main.AsyncDebouncer"), \
         patch("main.SkeletonEventBridge"), \
         patch("main.asyncio.sleep", side_effect=asyncio.CancelledError):
        import main
        try:
            asyncio.run(main.serve(
                repo_dir="/projects/test",
                target_url="http://localhost:8000",
                extensions=[".py"],
                project_name="test",
                secret_token="token",
            ))
        except asyncio.CancelledError:
            pass

    mock_polling.assert_called_once_with(timeout=1.0)


def test_serve_passes_polling_interval_to_observer():
    """
    Custom polling_interval must be forwarded to PollingObserver(timeout=...).
    """
    mock_outbox_instance = MagicMock()
    mock_outbox_instance.setup = AsyncMock()
    mock_outbox_instance.flush_pending_batched = AsyncMock()
    mock_outbox_instance.background_flush_loop = AsyncMock()
    mock_outbox_instance.close = AsyncMock()

    mock_client_instance = MagicMock()
    mock_client_instance.close = AsyncMock()
    mock_client_instance._make_deliver_fn = MagicMock()

    with patch("main.PollingObserver") as mock_polling, \
         patch("main.MCPClient", return_value=mock_client_instance), \
         patch("main.WorkerOutbox", return_value=mock_outbox_instance), \
         patch("main.AsyncDebouncer"), \
         patch("main.SkeletonEventBridge"), \
         patch("main.asyncio.sleep", side_effect=asyncio.CancelledError):
        import main
        try:
            asyncio.run(main.serve(
                repo_dir="/projects/test",
                target_url="http://localhost:8000",
                extensions=[".py"],
                project_name="test",
                secret_token="token",
                polling_interval=5.0,
            ))
        except asyncio.CancelledError:
            pass

    mock_polling.assert_called_once_with(timeout=5.0)
