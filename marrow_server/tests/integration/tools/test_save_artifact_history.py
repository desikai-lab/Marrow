import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.artifacts import save_artifact_logic
from utils.exceptions import ValidationError

PROJECT = "TestProject"


class TestSaveArtifactHistoryIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.project_path = Path(self.tmp) / PROJECT
        self.artifacts_dir = self.project_path / "artifacts"
        (self.artifacts_dir / "docs" / "sessions").mkdir(parents=True)
        self.history_path = self.artifacts_dir / "docs" / "sessions" / "history.md"

        self.patchers = [
            patch("config.PROJECTS_ROOT", self.tmp),
            patch("tools.utils.filesystem_utils.PROJECTS_ROOT", self.tmp),
            patch("tools.artifacts.validate_artifact_path", self._mock_validate_path),
            patch("tools.artifacts.create_artifact_backup", lambda project, rel_path: None),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mock_validate_path(self, project: str, rel_path: str) -> str:
        return str(self.history_path)

    def test_saveArtifactLogic_patchPrependsHistoryMd_newEntryAtTop(self):
        first_line = "## 2026-07-04 -- old entry\n"
        with open(self.history_path, "w", newline="\n", encoding="utf-8") as f:
            f.write(first_line + "body\n")

        new_content = "## 2026-07-08 -- new entry\n\n" + first_line
        save_artifact_logic(
            PROJECT, "docs/sessions/history.md", new_content, mode="patch", old_str=first_line
        )

        result = self.history_path.read_text(encoding="utf-8-sig")
        self.assertTrue(result.startswith("## 2026-07-08 -- new entry"))
        self.assertIn("## 2026-07-04 -- old entry", result)

    def test_saveArtifactLogic_replaceFileOnHistoryMd_rejectedEvenOnBrandNewProject(self):
        # file does not exist initially
        with self.assertRaises(ValidationError):
            save_artifact_logic(
                PROJECT, "docs/sessions/history.md", "## first entry\n", mode="replace_file"
            )


if __name__ == "__main__":
    unittest.main()
