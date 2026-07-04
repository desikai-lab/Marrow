import asyncio
import os
import shutil
import sys
import unittest
from datetime import datetime
from unittest.mock import patch

# Add project root to paths
sys.path.append(os.getcwd())

from config import PROJECTS_ROOT
from storage.uow import UnitOfWork
from tools.artifacts import move_project_artifact_logic

FAKE_VECTOR = [0.1] * 384


class TestMoveProjectArtifactLogicVectorSync(unittest.TestCase):
    def setUp(self):
        self.project = "test_move_sync_internal"
        self.project_root = os.path.join(PROJECTS_ROOT, self.project)

        if os.path.exists(self.project_root):
            try:
                shutil.rmtree(self.project_root)
            except Exception:
                pass
        os.makedirs(self.project_root, exist_ok=True)
        os.makedirs(os.path.join(self.project_root, "artifacts"), exist_ok=True)

        # Initialize database
        from storage.db import init_db

        init_db(self.project_root)

        # Mock embeddings globally
        self.embeddings_patcher = patch(
            "storage.embeddings.embeddings_manager.generate_vector",
            return_value=FAKE_VECTOR,
        )
        self.mock_generate_vector = self.embeddings_patcher.start()

    def tearDown(self):
        self.embeddings_patcher.stop()
        try:
            if os.path.exists(self.project_root):
                shutil.rmtree(self.project_root)
        except Exception:
            pass

    def test_moveProjectArtifactLogic_chunkedArtifact_chunksFollowToNewPath(self):
        # Create a real file on disk
        old_path = "a.md"
        new_path = "b.md"
        abs_old = os.path.join(self.project_root, "artifacts", old_path)
        with open(abs_old, "w", encoding="utf-8") as f:
            f.write("# H1\nSome test content")

        uow = UnitOfWork(self.project_root)
        asyncio.run(
            uow.chunks.upsert_chunks(
                old_path, "# H1\nSome test content", datetime.now().isoformat()
            )
        )

        # Call move_project_artifact_logic
        res = asyncio.run(move_project_artifact_logic(self.project, old_path, new_path))
        self.assertIn("Artifact moved: a.md -> b.md", res)
        self.assertNotIn("WARNING", res)

        # Assert files on disk
        abs_new = os.path.join(self.project_root, "artifacts", new_path)
        self.assertTrue(os.path.exists(abs_new))
        self.assertFalse(os.path.exists(abs_old))

        # Use a fresh UoW to avoid stale table handle — the move creates its own UoW internally
        uow2 = UnitOfWork(self.project_root)
        results = asyncio.run(uow2.chunks.semantic_search("test content", limit=10))
        self.assertTrue(any(r["path"] == new_path for r in results))
        self.assertFalse(any(r["path"] == old_path for r in results))

    def test_moveProjectArtifactLogic_neverChunkedArtifact_fallbackUpsertIndexesAtNewPath(self):
        old_path = "never_chunked.md"
        new_path = "now_chunked.md"
        abs_old = os.path.join(self.project_root, "artifacts", old_path)
        with open(abs_old, "w", encoding="utf-8") as f:
            f.write("# Fallback\nThis artifact has never been chunked before")

        res = asyncio.run(move_project_artifact_logic(self.project, old_path, new_path))
        self.assertIn("Artifact moved: never_chunked.md -> now_chunked.md", res)
        self.assertNotIn("WARNING", res)

        # Check that it's chunked and indexed at the new path
        uow = UnitOfWork(self.project_root)
        results = asyncio.run(uow.chunks.semantic_search("never been chunked", limit=10))
        self.assertTrue(any(r["path"] == new_path for r in results))

    def test_moveProjectArtifactLogic_chunkSyncRaises_returnsWarningInStringNotSilentSuccess(self):
        old_path = "failing_sync.md"
        new_path = "target.md"
        abs_old = os.path.join(self.project_root, "artifacts", old_path)
        with open(abs_old, "w", encoding="utf-8") as f:
            f.write("# Error\nSome content")

        uow = UnitOfWork(self.project_root)
        asyncio.run(
            uow.chunks.upsert_chunks(old_path, "# Error\nSome content", datetime.now().isoformat())
        )

        # Mock uow.chunks.rename to raise an error
        with patch.object(
            uow.chunks, "rename", side_effect=Exception("Database connection timed out")
        ):
            # We patch UnitOfWork constructor or the local instances, but since UnitOfWork is instantiated inside
            # move_project_artifact_logic, we can patch UnitOfWork's chunks property or patch uow.chunks.rename class-level.
            with patch(
                "storage.repositories.artifact_repository.ArtifactChunkRepository.rename",
                side_effect=Exception("Database connection timed out"),
            ):
                res = asyncio.run(move_project_artifact_logic(self.project, old_path, new_path))
                self.assertIn("WARNING: index sync failed: Database connection timed out", res)

        # The file should still be moved on disk
        abs_new = os.path.join(self.project_root, "artifacts", new_path)
        self.assertTrue(os.path.exists(abs_new))
        self.assertFalse(os.path.exists(abs_old))

    def test_moveProjectArtifactLogic_sourceNotFound_returnsNotFoundMessageNoIndexTouch(self):
        # Call with non-existent source
        res = asyncio.run(move_project_artifact_logic(self.project, "ghost.md", "real.md"))
        self.assertEqual(res, "Source file ghost.md not found.")


if __name__ == "__main__":
    unittest.main()
