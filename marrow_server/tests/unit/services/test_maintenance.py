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

        self.mock_artifact_pruner = AsyncMock()
        self.mock_artifact_pruner.prune.return_value = 0

        self.service_with_pruner = MaintenanceService(
            project_root="/tmp/test_project",
            project_name="TestProject",
            skeleton_repo=self.mock_repo,
            older_than_hours=2,
            artifact_ghost_pruner=self.mock_artifact_pruner,
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

    async def test_run_without_artifact_pruner_returns_zero_and_no_errors(self):
        """self.service was built without artifact_ghost_pruner (defaults to None)."""
        report = await self.service.run()

        self.assertEqual(report.artifact_chunks_pruned, 0)
        self.assertEqual(len(report.errors), 0)

    async def test_run_with_artifact_pruner_calls_prune_and_records_count(self):
        self.mock_artifact_pruner.prune.return_value = 3

        report = await self.service_with_pruner.run()

        self.assertEqual(report.artifact_chunks_pruned, 3)
        self.mock_artifact_pruner.prune.assert_called_once_with("TestProject")
        self.assertEqual(len(report.errors), 0)

    async def test_run_artifact_pruning_failure_isolated_other_phases_still_succeed(self):
        self.mock_artifact_pruner.prune.side_effect = Exception("Artifact pruning failed")

        report = await self.service_with_pruner.run()

        self.assertEqual(report.artifact_chunks_pruned, 0)
        self.assertTrue(report.versions_cleaned)
        self.assertTrue(report.files_compacted)
        self.assertTrue(
            any("Failed to prune artifact chunk ghost records" in err for err in report.errors),
            f"Errors: {report.errors}",
        )

    async def test_run_artifact_pruning_does_not_block_version_cleanup_failure_reporting(self):
        """Both an existing phase and the new phase fail in the same run — both
        errors must be reported, proving isolation runs in both directions."""
        self.mock_repo.cleanup_old_versions.side_effect = Exception("Cleanup failed")
        self.mock_artifact_pruner.prune.side_effect = Exception("Artifact pruning failed")

        report = await self.service_with_pruner.run()

        self.assertEqual(len(report.errors), 2)
        self.assertTrue(any("Version cleanup failed" in err for err in report.errors))
        self.assertTrue(
            any("Failed to prune artifact chunk ghost records" in err for err in report.errors)
        )


if __name__ == "__main__":
    unittest.main()
