import os
import shutil
import unittest
from unittest.mock import MagicMock, patch
from storage.repositories.skeleton_repository import SkeletonRepository
from config import PROJECTS_ROOT

class TestMaintenanceSafeCleanup(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.project = "test_maintenance_safe_cleanup"
        self.project_root = os.path.join(PROJECTS_ROOT, self.project)
        if not os.path.exists(self.project_root):
            os.makedirs(self.project_root)
        self.repo = SkeletonRepository(self.project_root)

    async def asyncTearDown(self):
        if os.path.exists(self.project_root):
            shutil.rmtree(self.project_root, ignore_errors=True)

    @patch("storage.db.get_db")
    async def test_cleanup_skips_single_version(self, mock_get_db):
        # Setup
        mock_db = MagicMock()
        mock_db.list_tables.return_value = ["test_table"]
        mock_get_db.return_value = mock_db
        
        mock_table = MagicMock()
        mock_table.version = 1
        mock_table.cleanup_old_versions = MagicMock()
        mock_db.open_table.return_value = mock_table
        
        # Run
        await self.repo.cleanup_old_versions(older_than_hours=1)
        
        # Verify
        mock_table.cleanup_old_versions.assert_not_called()

    @patch("storage.db.get_db")
    async def test_cleanup_runs_on_multiple_versions(self, mock_get_db):
        # Setup
        mock_db = MagicMock()
        mock_db.list_tables.return_value = ["test_table"]
        mock_get_db.return_value = mock_db
        
        mock_table = MagicMock()
        mock_table.version = 3
        mock_table.cleanup_old_versions = MagicMock()
        mock_db.open_table.return_value = mock_table
        
        # Run
        await self.repo.cleanup_old_versions(older_than_hours=1)
        
        # Verify
        mock_table.cleanup_old_versions.assert_called_once()
