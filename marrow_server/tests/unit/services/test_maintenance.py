import unittest
from unittest.mock import AsyncMock, MagicMock

from services.maintenance_service import MaintenanceService


class TestMaintenanceService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_repo = MagicMock()
        self.mock_repo.table = MagicMock()
        self.mock_repo.table.name = "test_table"
        self.mock_repo.table.count_rows.return_value = 10
        self.mock_repo.delete_file_chunks = AsyncMock()
        self.mock_repo.cleanup_old_versions = AsyncMock()
        self.mock_repo.compact_files = AsyncMock()
        self.mock_repo.get_all_indexed_paths = AsyncMock()

        self.service = MaintenanceService(
            project_root="/tmp/test_project",
            project_name="TestProject",
            skeleton_repo=self.mock_repo,
            older_than_hours=2,
        )

    async def test_run_completes_cleanup_and_compaction_but_skips_disabled_ghost_pruning(self):
        """Verifies that run() executes phase 1 and 2, but skip phase 3 (ghost pruning) as it is disabled."""
        report = await self.service.run()

        self.assertTrue(report.versions_cleaned)
        self.assertTrue(report.files_compacted)
        self.assertEqual(report.ghosts_pruned, 0)
        self.assertEqual(len(report.errors), 0)

        self.mock_repo.cleanup_old_versions.assert_called_once_with(2)
        self.mock_repo.compact_files.assert_called_once()
        self.mock_repo.get_all_indexed_paths.assert_not_called()

    async def test_run_version_cleanup_fails_other_phases_still_execute(self):
        self.mock_repo.cleanup_old_versions.side_effect = Exception("Cleanup failed")

        report = await self.service.run()

        self.assertFalse(report.versions_cleaned)
        self.assertTrue(report.files_compacted)
        self.assertTrue(
            any("Version cleanup failed" in err for err in report.errors),
            f"Errors: {report.errors}",
        )

        # Verify compact was still attempted, but prune is disabled
        self.mock_repo.compact_files.assert_called_once()
        self.mock_repo.get_all_indexed_paths.assert_not_called()

    async def test_run_empty_table_skips_ghost_pruning(self):
        self.mock_repo.table.count_rows.return_value = 0

        report = await self.service.run()

        self.assertEqual(report.ghosts_pruned, 0)
        self.mock_repo.get_all_indexed_paths.assert_not_called()


if __name__ == "__main__":
    unittest.main()
