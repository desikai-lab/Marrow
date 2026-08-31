import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.utils.history_integrity import HistoryMdIntegrityHook
from utils.exceptions import ValidationError

PROJECT = "TestProject"


class TestHistoryMdIntegrityHook(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.hook = HistoryMdIntegrityHook()
        self.tmp = tempfile.mkdtemp()
        self.project_path = Path(self.tmp) / PROJECT
        (self.project_path / "artifacts" / "docs" / "sessions").mkdir(parents=True)
        self.patchers = [
            patch("config.PROJECTS_ROOT", self.tmp),
            patch("tools.utils.history_integrity.validate_artifact_path", self._mock_validate_path),
        ]
        for p in self.patchers:
            p.start()

        self.history_path = self.project_path / "artifacts" / "docs" / "sessions" / "history.md"

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mock_validate_path(self, project: str, rel_path: str) -> str:
        return str(self.history_path)

    async def test_validateAndRepair_replaceFile_alwaysRaisesEvenOnMissingFile(self):
        with self.assertRaises(ValidationError):
            await self.hook.validate_and_repair(
                PROJECT, "docs/sessions/history.md", "## new -- content\n", "replace_file"
            )

    async def test_validateAndRepair_replaceFile_alwaysRaisesOnExistingFile(self):
        self.history_path.write_text("## 2026-07-04 -- old entry\n", encoding="utf-8")
        with self.assertRaises(ValidationError):
            await self.hook.validate_and_repair(
                PROJECT, "docs/sessions/history.md", "## new -- overwrite\n", "replace_file"
            )

    async def test_validateAndRepair_patchOnMissingFileWithEmptyOldStr_createsFileAndWritesContent(self):
        first_entry = "## 2026-07-08 -- first entry ever\n"
        result = await self.hook.validate_and_repair(
            PROJECT, "docs/sessions/history.md", first_entry, "patch", old_str=""
        )
        self.assertEqual(result, first_entry)
        self.assertTrue(self.history_path.exists())
        self.assertEqual(self.history_path.read_text(encoding="utf-8"), "")

    async def test_validateAndRepair_patchOnMissingFileWithNonEmptyOldStr_raisesValidationError(self):
        with self.assertRaises(ValidationError):
            await self.hook.validate_and_repair(
                PROJECT, "docs/sessions/history.md", "content\n", "patch", old_str="some old line\n"
            )

    async def test_validateAndRepair_patchAnchoredAtFirstLine_allowsPrepend(self):
        first_line = "## 2026-07-04 -- old entry\n"
        self.history_path.write_text(first_line + "body text\n", encoding="utf-8")
        new_content = "## 2026-07-08 -- new entry\n\n" + first_line
        result = await self.hook.validate_and_repair(
            PROJECT, "docs/sessions/history.md", new_content, "patch", old_str=first_line
        )
        self.assertEqual(result, new_content)

    async def test_validateAndRepair_patchOldStrNotAtStart_raisesValidationError(self):
        self.history_path.write_text(
            "## 2026-07-04 -- old entry\nmiddle text\n## 2026-05-19 -- older\n", encoding="utf-8"
        )
        with self.assertRaises(ValidationError):
            await self.hook.validate_and_repair(
                PROJECT,
                "docs/sessions/history.md",
                "edited middle\n",
                "patch",
                old_str="middle text\n",
            )

    async def test_validateAndRepair_disallowedModes_raisesValidationError(self):
        self.history_path.write_text("## 2026-07-04 -- old entry\n", encoding="utf-8")
        for mode in ["append_section", "replace_section", "delete_section", "replace_chunk"]:
            with self.subTest(mode=mode):
                with self.assertRaises(ValidationError):
                    await self.hook.validate_and_repair(
                        PROJECT, "docs/sessions/history.md", "content\n", mode
                    )


if __name__ == "__main__":
    unittest.main()
