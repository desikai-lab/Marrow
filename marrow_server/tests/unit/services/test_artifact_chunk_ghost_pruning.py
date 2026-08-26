import asyncio
import os
import shutil
import sys
import unittest
from datetime import datetime
from unittest.mock import patch

sys.path.append(os.getcwd())

from config import PROJECTS_ROOT
from storage.uow import UnitOfWork

FAKE_VECTOR = [0.1] * 384


class TestArtifactChunkRepositoryGhostPruningMethods(unittest.TestCase):
    def setUp(self):
        self.project = "test_chunk_ghost_pruning_internal"
        self.project_root = os.path.join(PROJECTS_ROOT, self.project)

        if os.path.exists(self.project_root):
            try:
                shutil.rmtree(self.project_root)
            except Exception:
                pass
        os.makedirs(self.project_root, exist_ok=True)
        os.makedirs(os.path.join(self.project_root, "artifacts"), exist_ok=True)

        from storage.db import init_db

        init_db(self.project_root)

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

    def test_count_rows_empty_table_returns_zero(self):
        uow = UnitOfWork(self.project_root)
        count = asyncio.run(uow.chunks.count_rows())
        self.assertEqual(count, 0)

    def test_count_rows_after_upsert_returns_nonzero(self):
        uow = UnitOfWork(self.project_root)
        asyncio.run(uow.chunks.upsert_chunks("a.md", "# H1\ncontent", datetime.now().isoformat()))

        count = asyncio.run(uow.chunks.count_rows())

        self.assertGreaterEqual(count, 1)

    def test_get_all_indexed_paths_dedupes_multi_chunk_file(self):
        uow = UnitOfWork(self.project_root)
        content = "## H2\nSome initial content\n\n## H3\nSecond section content"
        asyncio.run(uow.chunks.upsert_chunks("multi.md", content, datetime.now().isoformat()))

        table_rows = uow.chunks.table.search().to_list()
        self.assertGreaterEqual(len(table_rows), 2, "fixture must produce >1 chunk row")

        paths = asyncio.run(uow.chunks.get_all_indexed_paths(self.project))

        self.assertEqual(paths, ["multi.md"])

    def test_get_all_indexed_paths_returns_all_distinct_paths(self):
        uow = UnitOfWork(self.project_root)
        asyncio.run(uow.chunks.upsert_chunks("a.md", "# H1\ncontent a", datetime.now().isoformat()))
        asyncio.run(uow.chunks.upsert_chunks("b.md", "# H1\ncontent b", datetime.now().isoformat()))

        paths = asyncio.run(uow.chunks.get_all_indexed_paths(self.project))

        self.assertEqual(sorted(paths), ["a.md", "b.md"])

    def test_delete_chunks_by_path_removes_all_rows_for_path_only(self):
        uow = UnitOfWork(self.project_root)
        multi_content = "## H2\nSection one\n\n## H3\nSection two"
        asyncio.run(uow.chunks.upsert_chunks("target.md", multi_content, datetime.now().isoformat()))
        asyncio.run(uow.chunks.upsert_chunks("keep.md", "# H1\nkeep me", datetime.now().isoformat()))

        deleted_count = asyncio.run(uow.chunks.delete_chunks_by_path("target.md", self.project))

        remaining_rows = uow.chunks.table.search().to_list()
        remaining_paths = {r["path"] for r in remaining_rows}
        self.assertGreaterEqual(deleted_count, 2)
        self.assertNotIn("target.md", remaining_paths)
        self.assertIn("keep.md", remaining_paths)

    def test_delete_chunks_by_path_nonexistent_path_returns_zero(self):
        uow = UnitOfWork(self.project_root)

        deleted_count = asyncio.run(uow.chunks.delete_chunks_by_path("never-indexed.md", self.project))

        self.assertEqual(deleted_count, 0)


if __name__ == "__main__":
    unittest.main()
