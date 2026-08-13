import argparse
import os
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from cli.commands.reindex_chunks import ReindexChunksCommand


class TestReindexChunksCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.project_name = "TestProject"
        self.project_root = os.path.join(self.tmp, self.project_name)
        os.makedirs(self.project_root, exist_ok=True)

        self.mock_repo_instance = MagicMock()
        self.mock_repo_instance.table.delete = MagicMock()
        self.mock_repo_instance.upsert_chunks = AsyncMock(return_value=None)

        self.patchers = [
            patch("config.PROJECTS_ROOT", self.tmp),
            patch("storage.init_db", MagicMock()),
            patch(
                "storage.repositories.ArtifactChunkRepository",
                return_value=self.mock_repo_instance,
            ),
            patch(
                "tools.utils.cleaner.ContentCleaner.clean",
                side_effect=lambda content: f"CLEANED:{content}",
            ),
        ]
        for p in self.patchers:
            p.start()

        self.command = ReindexChunksCommand()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_file(self, rel_path: str, content: str = "# Hello\n\nBody.\n") -> None:
        full_path = os.path.join(self.project_root, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _make_args(self, dry_run: bool = False, file=None) -> argparse.Namespace:
        return argparse.Namespace(project=self.project_name, file=file, dry_run=dry_run)

    def test_execute_awaits_upsert_chunks_for_each_file(self):
        self._write_file("note.md")

        self.command.execute(self._make_args())

        self.mock_repo_instance.upsert_chunks.assert_awaited_once()
        call_args = self.mock_repo_instance.upsert_chunks.await_args
        self.assertEqual(call_args.args[0], "note.md")
        self.assertEqual(call_args.args[1], "CLEANED:# Hello\n\nBody.\n")
        self.assertEqual(call_args.kwargs["ext"], ".md")

    def test_dry_run_never_awaits_upsert_chunks(self):
        self._write_file("note.md")

        self.command.execute(self._make_args(dry_run=True))

        self.mock_repo_instance.upsert_chunks.assert_not_awaited()

    def test_execute_continues_after_one_file_errors(self):
        self._write_file("a.md")
        self._write_file("b.md")
        self.mock_repo_instance.upsert_chunks.side_effect = [RuntimeError("boom"), None]

        # Must not raise -- per-file errors are caught and logged, not propagated.
        self.command.execute(self._make_args())

        self.assertEqual(self.mock_repo_instance.upsert_chunks.await_count, 2)


if __name__ == "__main__":
    unittest.main()
