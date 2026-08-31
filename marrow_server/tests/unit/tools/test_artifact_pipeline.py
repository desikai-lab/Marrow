import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.artifact_pipeline import save_project_artifacts_logic

PROJECT = "TestProject"


class TestArtifactPipelineUnknownFields(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.artifacts = Path(self.tmp) / PROJECT / "artifacts"
        self.artifacts.mkdir(parents=True)
        (self.artifacts / "test.md").write_text(
            "# Title\n\n## Section A\nContent A\n", encoding="utf-8"
        )
        self.patchers = [
            patch("config.PROJECTS_ROOT", self.tmp),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    async def test_saveProjectArtifacts_withUnknownField_returnsWarningAndApplies(self):
        updates = [
            {
                "path": "test.md",
                "mode": "replace_file",
                "content": "New content",
                "old_str": "unused",
                "_explicit_fields": {"path", "mode", "content", "old_str"},
            }
        ]
        results = await save_project_artifacts_logic(PROJECT, updates)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "success")
        self.assertIn("warning", results[0])
        self.assertIn("old_str", results[0]["warning"])

    async def test_saveProjectArtifacts_validFieldsOnly_noWarning(self):
        updates = [
            {
                "path": "test.md",
                "mode": "replace_file",
                "content": "Clean content",
                "_explicit_fields": {"path", "mode", "content"},
            }
        ]
        results = await save_project_artifacts_logic(PROJECT, updates)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "success")
        self.assertNotIn("warning", results[0])


if __name__ == "__main__":
    unittest.main()
