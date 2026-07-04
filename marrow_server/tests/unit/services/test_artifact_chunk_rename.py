import asyncio
import os
import shutil
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add project root to paths
sys.path.append(os.getcwd())

from config import PROJECTS_ROOT
from storage.uow import UnitOfWork

FAKE_VECTOR = [0.1] * 384


class TestArtifactChunkRepositoryRename(unittest.TestCase):
    def setUp(self):
        self.project = "test_chunk_rename_internal"
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

        # Mock embeddings globally for this test class
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

    def test_rename_singleChunkFile_renamesRow(self):
        uow = UnitOfWork(self.project_root)
        content = "# H1\nsingle chunk content"
        updated = datetime.now().isoformat()

        # Upsert chunk
        asyncio.run(uow.chunks.upsert_chunks("a.md", content, updated))

        # Check it exists
        results_before = asyncio.run(uow.chunks.semantic_search("content", limit=10))
        self.assertTrue(any(r["path"] == "a.md" for r in results_before))

        # Rename
        renamed = asyncio.run(uow.chunks.rename("a.md", "b.md"))
        self.assertEqual(renamed, 1)

        # Check it moved to b.md
        results_after = asyncio.run(uow.chunks.semantic_search("content", limit=10))
        self.assertTrue(any(r["path"] == "b.md" for r in results_after))
        self.assertFalse(any(r["path"] == "a.md" for r in results_after))

    def test_rename_multiSectionFile_renamesAllRowsNotJustOne(self):
        uow = UnitOfWork(self.project_root)
        # Create multi-section content to produce multiple chunks
        content = "## H2\nSome initial content\n\n## H3\nSecond section content"
        updated = datetime.now().isoformat()

        asyncio.run(uow.chunks.upsert_chunks("a.md", content, updated))

        # Direct table search to see row count
        table_rows_before = (
            uow.chunks.table.search().where("path = 'a.md'", prefilter=True).to_list()
        )
        self.assertGreaterEqual(len(table_rows_before), 2)

        # Rename
        renamed = asyncio.run(uow.chunks.rename("a.md", "b.md"))
        self.assertEqual(renamed, len(table_rows_before))

        # Direct table search to verify paths
        table_rows_after = uow.chunks.table.search().to_list()
        self.assertTrue(all(r["path"] == "b.md" for r in table_rows_after))
        self.assertFalse(any(r["path"] == "a.md" for r in table_rows_after))

    def test_rename_pathNotIndexed_returnsZeroNoRowsAdded(self):
        uow = UnitOfWork(self.project_root)
        renamed = asyncio.run(uow.chunks.rename("never-indexed.md", "new.md"))
        self.assertEqual(renamed, 0)

        table_rows = uow.chunks.table.search().to_list()
        self.assertEqual(len(table_rows), 0)

    def test_rename_insertSucceedsDeleteFails_oldAndNewBothPresentNoDataLoss(self):
        uow = UnitOfWork(self.project_root)
        content = "# H1\nsingle chunk content"
        updated = datetime.now().isoformat()

        asyncio.run(uow.chunks.upsert_chunks("a.md", content, updated))

        # Patch table.delete to raise an error
        original_delete = uow.chunks.table.delete
        uow.chunks.table.delete = MagicMock(side_effect=Exception("Simulated delete failure"))

        try:
            renamed = asyncio.run(uow.chunks.rename("a.md", "b.md"))
            self.assertEqual(renamed, 1)

            # Retrieve all rows using original delete's underlying table or search
            uow.chunks.table.delete = original_delete

            rows = uow.chunks.table.search().to_list()
            paths = [r["path"] for r in rows]
            self.assertIn("a.md", paths)
            self.assertIn("b.md", paths)
        finally:
            uow.chunks.table.delete = original_delete


if __name__ == "__main__":
    unittest.main()
