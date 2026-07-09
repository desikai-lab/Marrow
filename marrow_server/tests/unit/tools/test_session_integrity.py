import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.utils.session_integrity import SessionMdIntegrityHook

GOOD_HEADER = (
    "# Session State — Proj\n**Current Task:** F1 — desc\n**next_agent_role:** Planning Agent\n\n"
)
PROJECT = "TestProject"


class TestSessionMdIntegrityHook(unittest.TestCase):
    def setUp(self):
        self.hook = SessionMdIntegrityHook()
        self.tmp = tempfile.mkdtemp()
        self.project_path = Path(self.tmp) / PROJECT
        (self.project_path / "artifacts").mkdir(parents=True)
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

    # ── mode guard ──────────────────────────────────────────────────────────

    def test_validateAndRepair_nonReplaceFileMode_contentUnchanged(self):
        """Non replace_file modes must never trigger the repair logic."""
        broken = "no header at all\n"
        result = self.hook.validate_and_repair(
            PROJECT, "session.md", broken, mode="replace_section"
        )
        self.assertEqual(result, broken)

    def test_validateAndRepair_patchMode_contentUnchanged(self):
        broken = "no header at all\n"
        result = self.hook.validate_and_repair(PROJECT, "session.md", broken, mode="patch")
        self.assertEqual(result, broken)

    # ── well-formed content ──────────────────────────────────────────────────

    def test_validateAndRepair_wellFormedContent_passesThroughUnchanged(self):
        content = GOOD_HEADER + "**Focus:** doing things\n"
        result = self.hook.validate_and_repair(PROJECT, "session.md", content, mode="replace_file")
        self.assertEqual(result, content)

    # ── malformed content with history ──────────────────────────────────────

    def test_validateAndRepair_malformedWithPriorBackup_repairsFromHistory(self):
        from tools.artifacts import save_artifact_logic

        # Seed a well-formed version so there's a backup
        save_artifact_logic(
            PROJECT, "session.md", GOOD_HEADER + "first write\n", mode="replace_file"
        )

        broken = "focus content only, no header\n"
        result = self.hook.validate_and_repair(PROJECT, "session.md", broken, mode="replace_file")

        self.assertIn("# Session State", result)
        self.assertIn("next_agent_role:", result)
        self.assertIn("focus content only", result)

    # ── malformed content with no history ───────────────────────────────────

    def test_validateAndRepair_malformedNoBackupYet_writesAsIs(self):
        broken = "no header at all on first write\n"
        result = self.hook.validate_and_repair(PROJECT, "session.md", broken, mode="replace_file")
        # No backup exists — gracefully degrades, returns content unchanged
        self.assertEqual(result, broken)

    # ── unreadable backup graceful degradation ───────────────────────────────

    def test_validateAndRepair_backupUnreadable_logsWarningAndContinues(self):
        """An OSError on a backup file must be logged and not escape validate_and_repair."""
        # Inject a fake history entry that points to a non-existent file
        fake_history = [{"backup_name": "nonexistent_backup_file.md"}]
        with (
            patch("tools.utils.session_integrity.get_artifact_history", return_value=fake_history),
            patch(
                "tools.utils.session_integrity.validate_artifact_path",
                side_effect=ValueError("no live file"),
            ),
            self.assertLogs("tools.utils.session_integrity", level="WARNING") as log_ctx,
        ):
            broken = "missing header\n"
            result = self.hook.validate_and_repair(
                PROJECT, "session.md", broken, mode="replace_file"
            )

        # No exception escapes
        self.assertEqual(result, broken)
        # Warning was logged (either from repair trigger or backup read failure)
        self.assertTrue(
            any("nonexistent_backup_file.md" in m or "session.md" in m for m in log_ctx.output)
        )

    def test_validate_and_repair_extraKwargsPassed_ignoredWithoutError(self):
        """Confirms the ABC widening to **kwargs doesn't break SessionMdIntegrityHook,
        which has no use for extra kwargs but must still accept them."""
        content = GOOD_HEADER + "**Focus:** doing things\n"
        result = self.hook.validate_and_repair(
            PROJECT,
            "session.md",
            content,
            "replace_file",
            old_str="irrelevant",
            section_name="also irrelevant",
        )
        self.assertEqual(result, content)


if __name__ == "__main__":
    unittest.main()
