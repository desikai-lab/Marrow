import asyncio
import os
import shutil
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from transport.app_factory import maintenance_loop


class TestMaintenanceScheduler(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_root = os.path.join(os.getcwd(), "test_scheduler_root")
        if os.path.exists(self.test_root):
            shutil.rmtree(self.test_root)
        os.makedirs(self.test_root)

        # Create two projects
        os.makedirs(os.path.join(self.test_root, "project1", ".db"))
        with open(os.path.join(self.test_root, "project1", ".db", "index.lancedb"), "w") as f:
            f.write("dummy")

        os.makedirs(os.path.join(self.test_root, "project2", ".db"))
        with open(os.path.join(self.test_root, "project2", ".db", "index.lancedb"), "w") as f:
            f.write("dummy")

    async def asyncTearDown(self):
        if os.path.exists(self.test_root):
            shutil.rmtree(self.test_root)

    @patch("services.maintenance_service.MaintenanceService")
    @patch("storage.repositories.artifact_repository.ArtifactChunkRepository")
    @patch("storage.repositories.skeleton_repository.SkeletonRepository")
    @patch("asyncio.sleep", return_value=None)
    async def test_loop_error_isolation(self, mock_sleep, mock_skeleton_repo, mock_artifact_repo, mock_service):

        # Patch config.PROJECTS_ROOT to point to our test directory
        with patch("config.PROJECTS_ROOT", self.test_root):
            # Setup mocks
            inst1 = AsyncMock()
            inst1.run.side_effect = RuntimeError("Project 1 failed")

            inst2 = AsyncMock()
            inst2.run.return_value = MagicMock(
                errors=[], files_compacted=True, versions_cleaned=True, ghosts_pruned=0
            )

            mock_service.side_effect = [inst1, inst2]

            # We only want to run one cycle
            mock_sleep.side_effect = [None, asyncio.CancelledError()]

            try:
                await maintenance_loop()
            except asyncio.CancelledError:
                pass

            # Verify both were called despite the first one failing
            self.assertEqual(mock_service.call_count, 2)

    @patch("services.maintenance_service.MaintenanceService")
    @patch("storage.repositories.artifact_repository.ArtifactChunkRepository")
    @patch("storage.repositories.skeleton_repository.SkeletonRepository")
    @patch("asyncio.sleep", return_value=None)
    async def test_loop_wires_artifact_ghost_pruner_into_maintenance_service(
        self, mock_sleep, mock_skeleton_repo, mock_artifact_repo, mock_service
    ):
        from storage.ghost_pruner import GhostPruner

        with patch("config.PROJECTS_ROOT", self.test_root):
            inst = AsyncMock()
            inst.run.return_value = MagicMock(
                errors=[],
                files_compacted=True,
                versions_cleaned=True,
                ghosts_pruned=0,
                artifact_chunks_pruned=0,
            )
            mock_service.side_effect = [inst, inst]

            mock_sleep.side_effect = [None, asyncio.CancelledError()]

            try:
                await maintenance_loop()
            except asyncio.CancelledError:
                pass

            self.assertEqual(mock_service.call_count, 2)
            for call in mock_service.call_args_list:
                _, kwargs = call
                self.assertIn("artifact_ghost_pruner", kwargs)
                self.assertIsInstance(kwargs["artifact_ghost_pruner"], GhostPruner)

