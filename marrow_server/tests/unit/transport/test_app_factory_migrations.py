import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from transport.app_factory import lifespan


@pytest.mark.asyncio
async def test_lifespan_normal_startup_calls_run_migrations_all_projects_before_session_manager_run():
    call_order = []

    def fake_migrations(*args, **kwargs):
        call_order.append("migrations")
        return []

    session_cm = MagicMock()

    async def fake_aenter():
        call_order.append("session_manager")
        return None

    session_cm.__aenter__ = AsyncMock(side_effect=fake_aenter)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    def dummy_task(*args, **kwargs):
        fut = asyncio.Future()
        fut.set_result(None)
        return fut

    with (
        patch("migrator.runner.run_migrations_all_projects", side_effect=fake_migrations) as mock_migrate,
        patch("transport.app_factory.asyncio.create_task", side_effect=dummy_task),
        patch("transport.app_factory.mcp") as mock_mcp,
    ):
        mock_mcp.session_manager.run.return_value = session_cm
        app = MagicMock()
        async with lifespan(app):
            pass

    mock_migrate.assert_called_once()
    assert call_order == ["migrations", "session_manager"]


@pytest.mark.asyncio
async def test_lifespan_migration_runner_raises_logs_and_still_starts_serving():
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=None)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    def dummy_task(*args, **kwargs):
        fut = asyncio.Future()
        fut.set_result(None)
        return fut

    with (
        patch("migrator.runner.run_migrations_all_projects", side_effect=RuntimeError("boom")),
        patch("transport.app_factory.asyncio.create_task", side_effect=dummy_task),
        patch("transport.app_factory.mcp") as mock_mcp,
        patch("transport.app_factory._logging.getLogger") as mock_get_logger,
    ):
        mock_mcp.session_manager.run.return_value = session_cm
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        app = MagicMock()
        async with lifespan(app):
            pass

    mock_logger.error.assert_called_once()
    session_cm.__aenter__.assert_called_once()

