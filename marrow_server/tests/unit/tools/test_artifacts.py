import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.artifact_pipeline import save_project_artifacts_logic

PROJECT = "TestProject"


class TestSaveArtifactLogicSessionMdValidation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.artifacts = Path(self.tmp) / PROJECT / "artifacts"
        self.artifacts.mkdir(parents=True)
        self.patchers = [
            patch("config.PROJECTS_ROOT", self.tmp),
            patch("tools.utils.filesystem_utils.PROJECTS_ROOT", self.tmp),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    async def test_saveArtifactLogic_validSessionMdHeader_writtenUnchanged(self):
        good = (
            "# Session State — Proj\n"
            "**Current Task:** F1 — desc\n"
            "**next_agent_role:** Planning Agent\n\n"
            "**Focus:** doing things\n"
        )
        await save_project_artifacts_logic(
            PROJECT, [{"path": "session.md", "content": good, "mode": "replace_file"}]
        )
        written = (self.artifacts / "session.md").read_text(encoding="utf-8-sig")
        self.assertEqual(written, good)

    async def test_saveArtifactLogic_nonSessionMdFile_validationSkipped(self):
        content = "not a session header at all"
        await save_project_artifacts_logic(
            PROJECT, [{"path": "spec.md", "content": content, "mode": "replace_file"}]
        )
        written = (self.artifacts / "spec.md").read_text(encoding="utf-8-sig")
        self.assertEqual(written, content)

    async def test_saveArtifactLogic_malformedHeaderWithPriorBackup_repairsFromBackup(self):
        good = (
            "# Session State — Proj\n"
            "**Current Task:** F1 — desc\n"
            "**next_agent_role:** Planning Agent\n\n"
            "**Focus:** first write\n"
        )
        await save_project_artifacts_logic(
            PROJECT, [{"path": "session.md", "content": good, "mode": "replace_file"}]
        )

        broken = "**Focus:** second write, header got clobbered\n"
        await save_project_artifacts_logic(
            PROJECT, [{"path": "session.md", "content": broken, "mode": "replace_file"}]
        )

        written = (self.artifacts / "session.md").read_text(encoding="utf-8-sig")
        self.assertTrue(written.startswith("# Session State — Proj"))
        self.assertIn("**next_agent_role:** Planning Agent", written)
        self.assertIn("second write, header got clobbered", written)

    async def test_saveArtifactLogic_malformedHeaderNoBackupYet_writesUnrepairedContent(self):
        broken = "no header at all on first write\n"
        await save_project_artifacts_logic(
            PROJECT, [{"path": "session.md", "content": broken, "mode": "replace_file"}]
        )
        written = (self.artifacts / "session.md").read_text(encoding="utf-8-sig")
        self.assertEqual(written, broken)


if __name__ == "__main__":
    unittest.main()
