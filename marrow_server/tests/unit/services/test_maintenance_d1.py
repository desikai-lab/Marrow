import unittest
from unittest.mock import MagicMock, AsyncMock
from services.maintenance_service import MaintenanceService

class TestMaintenanceD1(unittest.IsolatedAsyncioTestCase):
    async def test_ghost_prune_includes_tests(self):
        # Setup
        mock_repo = AsyncMock()
        mock_repo.table.count_rows.return_value = 10
        mock_repo.get_all_indexed_paths.return_value = []
        
        service = MaintenanceService(
            project_root="/tmp",
            project_name="test_proj",
            skeleton_repo=mock_repo
        )
        
        # Run
        await service._prune_ghost_records([])
        
        # Verify
        # Check if the call included include_tests=True (the D1 fix)
        mock_repo.get_all_indexed_paths.assert_called_once_with("test_proj", include_tests=True)
