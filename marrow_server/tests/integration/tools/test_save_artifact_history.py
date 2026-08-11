import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.artifact_pipeline import save_project_artifacts_logic

PROJECT = "TestIntegrationProject"


class TestSaveArtifactHistoryIntegration(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.project_path = Path(self.tmp) / PROJECT
        (self.project_path / "artifacts" / "sessions").mkdir(parents=True)
        self.patchers = [
            patch("config.PROJECTS_ROOT", self.tmp),
            patch("tools.utils.filesystem_utils.PROJECTS_ROOT", self.tmp),
        ]
        for p in self.patchers:
            p.start()

        self.session_path = self.project_path / "artifacts" / "session.md"
        self.history_path = self.project_path / "artifacts" / "sessions" / "history.md"

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    async def test_fullPipeline_genuineRoleTransition_prependsHistoryFile(self):
        # 1. Initial write of session.md (Planning Agent)
        initial_session = (
            "# Session State — TestIntegrationProject\n"
            "**Current Task:** F4000189 — Auto-append session.md to history.md\n"
            "**next_agent_role:** Planning Agent\n\n"
            "## Handover Note\n"
            "Planning finished and approved."
        )
        res1 = await save_project_artifacts_logic(
            PROJECT, [{"path": "session.md", "mode": "replace_file", "content": initial_session}]
        )
        self.assertEqual(res1[0]["status"], "success")
        self.assertFalse(self.history_path.exists())

        # 2. Genuine transition save (Planning Agent -> Execution Agent)
        new_session = (
            "# Session State — TestIntegrationProject\n"
            "**Current Task:** F4000189 — Auto-append session.md to history.md\n"
            "**next_agent_role:** Execution Agent\n\n"
            "## Handover Note\n"
            "Execution started."
        )
        res2 = await save_project_artifacts_logic(
            PROJECT, [{"path": "session.md", "mode": "replace_file", "content": new_session}]
        )
        self.assertEqual(res2[0]["status"], "success")

        # Verify history file created and contains old task + old handover note
        self.assertTrue(self.history_path.exists())
        history_text = self.history_path.read_text(encoding="utf-8-sig")
        # New format: ## Date — Task Title heading + **next_agent_role:** metadata + handover body
        self.assertIn("F4000189 — Auto-append session.md to history.md", history_text)  # task title in heading
        self.assertIn("**next_agent_role:** Planning Agent", history_text)  # departing agent role
        self.assertIn("Planning finished and approved.", history_text)  # handover body

        # 3. Second transition (Execution Agent -> Discovery Agent)
        final_session = (
            "# Session State — TestIntegrationProject\n"
            "**Current Task:** F4000189 — Auto-append session.md to history.md\n"
            "**next_agent_role:** Discovery Agent\n\n"
            "## Handover Note\n"
            "Execution complete."
        )
        res3 = await save_project_artifacts_logic(
            PROJECT, [{"path": "session.md", "mode": "replace_file", "content": final_session}]
        )
        self.assertEqual(res3[0]["status"], "success")

        # Verify history contains newest entry prepended first
        new_history_text = self.history_path.read_text(encoding="utf-8-sig")
        self.assertIn("Execution started.", new_history_text)
        # Check order: Execution started entry appears BEFORE Planning finished entry
        pos_exec = new_history_text.index("Execution started.")
        pos_plan = new_history_text.index("Planning finished and approved.")
        self.assertLess(pos_exec, pos_plan)


if __name__ == "__main__":
    unittest.main()
