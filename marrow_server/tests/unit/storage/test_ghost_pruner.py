import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from storage.ghost_pruner import FilesystemExistenceStrategy, GhostPruner


class TestFilesystemExistenceStrategy(unittest.IsolatedAsyncioTestCase):
    async def test_exists_returns_true_for_real_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "real.md").write_text("hello")
            strategy = FilesystemExistenceStrategy(root_resolver=lambda project: tmpdir)

            result = await strategy.exists("any_project", "real.md")

            self.assertTrue(result)

    async def test_exists_returns_false_for_missing_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = FilesystemExistenceStrategy(root_resolver=lambda project: tmpdir)

            result = await strategy.exists("any_project", "missing.md")

            self.assertFalse(result)


class TestGhostPruner(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_repo = AsyncMock()
        self.mock_strategy = AsyncMock()
        self.pruner = GhostPruner(repo=self.mock_repo, strategy=self.mock_strategy)

    async def test_prune_empty_table_short_circuits_without_calling_strategy(self):
        self.mock_repo.count_rows.return_value = 0

        result = await self.pruner.prune("proj")

        self.assertEqual(result, 0)
        self.mock_repo.get_all_indexed_paths.assert_not_called()
        self.mock_strategy.exists.assert_not_called()

    async def test_prune_existing_path_is_never_deleted(self):
        self.mock_repo.count_rows.return_value = 5
        self.mock_repo.get_all_indexed_paths.return_value = ["still_here.md"]
        self.mock_strategy.exists.return_value = True

        result = await self.pruner.prune("proj")

        self.assertEqual(result, 0)
        self.mock_repo.delete_chunks_by_path.assert_not_called()

    async def test_prune_missing_path_is_deleted_exactly_once(self):
        self.mock_repo.count_rows.return_value = 5
        self.mock_repo.get_all_indexed_paths.return_value = ["gone.md"]
        self.mock_strategy.exists.return_value = False

        result = await self.pruner.prune("proj")

        self.assertEqual(result, 1)
        self.mock_repo.delete_chunks_by_path.assert_called_once_with("gone.md", "proj")

    async def test_prune_mixed_paths_only_deletes_missing_ones(self):
        self.mock_repo.count_rows.return_value = 5
        self.mock_repo.get_all_indexed_paths.return_value = [
            "gone.md",
            "still_here.md",
            "also_gone.md",
        ]
        self.mock_strategy.exists.side_effect = lambda project, path: path == "still_here.md"

        result = await self.pruner.prune("proj")

        self.assertEqual(result, 2)
        self.assertEqual(self.mock_repo.delete_chunks_by_path.call_count, 2)

    async def test_prune_strategy_exception_propagates_to_caller(self):
        self.mock_repo.count_rows.return_value = 5
        self.mock_repo.get_all_indexed_paths.return_value = ["a.md"]
        self.mock_strategy.exists.side_effect = RuntimeError("strategy blew up")

        with self.assertRaises(RuntimeError):
            await self.pruner.prune("proj")


if __name__ == "__main__":
    unittest.main()
