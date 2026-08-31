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


class TestSessionMdIntegrityHook(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.hook = SessionMdIntegrityHook()
        self.tmp = tempfile.mkdtemp()
        self.project_path = Path(self.tmp) / PROJECT
        (self.project_path / "artifacts" / "sessions").mkdir(parents=True)
        self.patchers = [
            patch("config.PROJECTS_ROOT", self.tmp),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── mode guard ──────────────────────────────────────────────────────────

    async def test_validateAndRepair_nonReplaceFileMode_contentUnchanged(self):
        """Non replace_file modes must never trigger the repair logic."""
        broken = "no header at all\n"
        result = await self.hook.validate_and_repair(
            PROJECT, "session.md", broken, mode="replace_section"
        )
        self.assertEqual(result, broken)

    async def test_validateAndRepair_patchMode_contentUnchanged(self):
        broken = "no header at all\n"
        result = await self.hook.validate_and_repair(PROJECT, "session.md", broken, mode="patch")
        self.assertEqual(result, broken)

    # ── well-formed content ──────────────────────────────────────────────────

    async def test_validateAndRepair_wellFormedContent_passesThroughUnchanged(self):
        content = GOOD_HEADER + "**Focus:** doing things\n"
        result = await self.hook.validate_and_repair(
            PROJECT, "session.md", content, mode="replace_file"
        )
        self.assertEqual(result, content)

    # ── malformed content with history ──────────────────────────────────────

    async def test_validateAndRepair_malformedWithPriorBackup_repairsFromHistory(self):
        from tools.artifact_pipeline import save_project_artifacts_logic

        # Seed a well-formed version so there's a backup
        await save_project_artifacts_logic(
            PROJECT,
            [
                {
                    "path": "session.md",
                    "content": GOOD_HEADER + "first write\n",
                    "mode": "replace_file",
                }
            ],
        )

        broken = "focus content only, no header\n"
        result = await self.hook.validate_and_repair(
            PROJECT, "session.md", broken, mode="replace_file"
        )

        self.assertIn("# Session State", result)
        self.assertIn("next_agent_role:", result)
        self.assertIn("focus content only", result)

    # ── malformed content with no history ───────────────────────────────────

    async def test_validateAndRepair_malformedNoBackupYet_writesAsIs(self):
        broken = "no header at all on first write\n"
        result = await self.hook.validate_and_repair(
            PROJECT, "session.md", broken, mode="replace_file"
        )
        # No backup exists — gracefully degrades, returns content unchanged
        self.assertEqual(result, broken)

    # ── unreadable backup graceful degradation ───────────────────────────────

    async def test_validateAndRepair_backupUnreadable_logsWarningAndContinues(self):
        """An OSError on a backup file must be logged and not escape validate_and_repair."""
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
            result = await self.hook.validate_and_repair(
                PROJECT, "session.md", broken, mode="replace_file"
            )

        self.assertEqual(result, broken)
        self.assertTrue(
            any("nonexistent_backup_file.md" in m or "session.md" in m for m in log_ctx.output)
        )

    async def test_validate_and_repair_extraKwargsPassed_ignoredWithoutError(self):
        content = GOOD_HEADER + "**Focus:** doing things\n"
        result = await self.hook.validate_and_repair(
            PROJECT,
            "session.md",
            content,
            "replace_file",
            old_str="irrelevant",
            section_name="also irrelevant",
        )
        self.assertEqual(result, content)

    # ── genuine phase transition auto-append tests (REQ-01..REQ-05) ─────────────

    async def test_validateAndRepair_genuineRoleTransition_appendsHistoryEntry(self):
        from tools.artifact_pipeline import save_project_artifacts_logic

        old_session = (
            "# Session State — Proj\n"
            "**Current Task:** F1 — Old task\n"
            "**next_agent_role:** Planning Agent\n\n"
            "## Handover Note\n"
            "Planning finished successfully."
        )
        await save_project_artifacts_logic(
            PROJECT, [{"path": "session.md", "content": old_session, "mode": "replace_file"}]
        )

        new_session = (
            "# Session State — Proj\n"
            "**Current Task:** F1 — Old task\n"
            "**next_agent_role:** Execution Agent\n\n"
            "## Handover Note\n"
            "Execution in progress."
        )

        with patch("services.artifact_command_service.save_project_artifacts_logic") as mock_save:
            mock_save.return_value = []
            await self.hook.validate_and_repair(
                PROJECT, "session.md", new_session, mode="replace_file"
            )
            mock_save.assert_called_once()
            args, kwargs = mock_save.call_args
            project_arg, updates = args[0], args[1]
            self.assertEqual(project_arg, PROJECT)
            self.assertEqual(updates[0]["path"], "sessions/history.md")
            self.assertEqual(updates[0]["mode"], "patch")
            # New format: ## Date — Task Title heading + **next_agent_role:** metadata
            self.assertIn("F1 — Old task", updates[0]["content"])  # task title in heading
            self.assertIn(
                "**next_agent_role:** Planning Agent", updates[0]["content"]
            )  # departing role
            self.assertIn("Planning finished successfully.", updates[0]["content"])  # handover body

    async def test_validateAndRepair_sameRole_doesNotAppendHistory(self):
        from tools.artifact_pipeline import save_project_artifacts_logic

        old_session = (
            "# Session State — Proj\n"
            "**Current Task:** F1 — Old task\n"
            "**next_agent_role:** Execution Agent\n\n"
            "## Handover Note\n"
            "Step 1 done."
        )
        await save_project_artifacts_logic(
            PROJECT, [{"path": "session.md", "content": old_session, "mode": "replace_file"}]
        )

        new_session = (
            "# Session State — Proj\n"
            "**Current Task:** F1 — Old task\n"
            "**next_agent_role:** Execution Agent\n\n"
            "## Handover Note\n"
            "Step 2 done."
        )

        with patch("services.artifact_command_service.save_project_artifacts_logic") as mock_save:
            await self.hook.validate_and_repair(
                PROJECT, "session.md", new_session, mode="replace_file"
            )
            mock_save.assert_not_called()

    async def test_validateAndRepair_firstEverWrite_skipsHistory(self):
        new_session = (
            "# Session State — Proj\n"
            "**Current Task:** F1 — Old task\n"
            "**next_agent_role:** Execution Agent\n\n"
            "## Handover Note\n"
            "First write ever."
        )

        with patch("services.artifact_command_service.save_project_artifacts_logic") as mock_save:
            await self.hook.validate_and_repair(
                PROJECT, "session.md", new_session, mode="replace_file"
            )
            mock_save.assert_not_called()

    async def test_validateAndRepair_historyWriteFails_swallowsExceptionAndLogsWarning(self):
        from tools.artifact_pipeline import save_project_artifacts_logic

        old_session = (
            "# Session State — Proj\n"
            "**Current Task:** F1 — Old task\n"
            "**next_agent_role:** Planning Agent\n\n"
            "## Handover Note\n"
            "Planning finished."
        )
        await save_project_artifacts_logic(
            PROJECT, [{"path": "session.md", "content": old_session, "mode": "replace_file"}]
        )

        new_session = (
            "# Session State — Proj\n"
            "**Current Task:** F1 — Old task\n"
            "**next_agent_role:** Execution Agent\n\n"
            "## Handover Note\n"
            "Execution started."
        )

        with (
            patch(
                "services.artifact_command_service.save_project_artifacts_logic",
                side_effect=RuntimeError("Disk error writing history"),
            ),
            self.assertLogs("tools.utils.session_integrity", level="WARNING") as log_ctx,
        ):
            result = await self.hook.validate_and_repair(
                PROJECT, "session.md", new_session, mode="replace_file"
            )

        self.assertEqual(result, new_session)
        self.assertTrue(any("Failed to append history entry" in m for m in log_ctx.output))


class TestExtractHandoverBody(unittest.TestCase):
    def setUp(self):
        self.hook = SessionMdIntegrityHook()

    def test_extractHandoverBody_canonicalHeading_capturesBodyByteIdenticalToOriginal(self):
        old_content = (
            "# Session State\n\n"
            "**Current Task:** B1 \u2014 thing\n"
            "**next_agent_role:** discovery\n\n"
            "## Handover Note\n"
            "Do the thing.\n"
            "And more.\n"
        )
        body, used_fallback = self.hook._extract_handover_body(old_content)
        self.assertEqual(body, "Do the thing.\nAnd more.")
        self.assertFalse(used_fallback)

    def test_extractHandoverBody_boldLabelHeadingLike_capturesBodyAfterLabel(self):
        old_content = (
            "# Session State\n\n"
            "**Current Task:** B1 \u2014 thing\n"
            "**next_agent_role:** discovery\n"
            "**Handover to Discovery Agent:**\n"
            "- item1\n"
            "- item2\n"
        )
        body, used_fallback = self.hook._extract_handover_body(old_content)
        self.assertEqual(body, "- item1\n- item2")
        self.assertFalse(used_fallback)

    def test_extractHandoverBody_tier1BeatsTier2_prioritizesHeadingOverEarlierIncidentalMention(
        self,
    ):
        old_content = (
            "# Session State\n\n"
            "**Current Task:** B1 \u2014 thing\n"
            "**Task status:** DONE, no handover concerns from this session\n"
            "**next_agent_role:** discovery\n"
            "**Handover to Discovery Agent:**\n"
            "- Pick up next task from backlog.\n"
        )
        body, used_fallback = self.hook._extract_handover_body(old_content)
        self.assertEqual(body, "- Pick up next task from backlog.")
        self.assertFalse(used_fallback)

    def test_extractHandoverBody_tier2OnlyNoHeadingLike_usesIncidentalMentionLine(self):
        old_content = (
            "# Session State\n\n"
            "**Current Task:** B1 \u2014 thing\n"
            "**Task status:** DONE, no handover concerns from this session\n"
            "**next_agent_role:** discovery\n"
        )
        body, used_fallback = self.hook._extract_handover_body(old_content)
        self.assertEqual(body, "**next_agent_role:** discovery")
        self.assertFalse(used_fallback)

    def test_extractHandoverBody_noHandoverAnywhere_fallsBackToWholeBodyAfterHeader(self):
        old_content = (
            "# Session State\n\n**Current Task:** B1 \u2014 thing\n**next_agent_role:** discovery\n"
        )
        body, used_fallback = self.hook._extract_handover_body(old_content)
        self.assertEqual(body, "**Current Task:** B1 \u2014 thing\n**next_agent_role:** discovery")
        self.assertTrue(used_fallback)

    def test_extractHandoverBody_headingLikeLineIsLastLineWithEmptyCapture_fallsBackToWholeBody(
        self,
    ):
        old_content = (
            "# Session State\n\n"
            "**Current Task:** B1 \u2014 thing\n"
            "**next_agent_role:** discovery\n"
            "## Handover Note"
        )
        body, used_fallback = self.hook._extract_handover_body(old_content)
        self.assertEqual(
            body,
            "**Current Task:** B1 \u2014 thing\n**next_agent_role:** discovery\n## Handover Note",
        )
        self.assertTrue(used_fallback)


class TestBuildHistoryEntry(unittest.TestCase):
    def setUp(self):
        self.hook = SessionMdIntegrityHook()

    @patch("tools.utils.session_integrity.date")
    def test_buildHistoryEntry_canonicalHeading_preservesOriginalFormattingByteIdentical(
        self, mock_date
    ):
        mock_date.today.return_value.isoformat.return_value = "2026-08-16"
        old_content = (
            "# Session State\n\n"
            "**Current Task:** B4000203 \u2014 history.md entries silently drop Handover\n"
            "**next_agent_role:** execution\n\n"
            "## Handover Note\n"
            "- item 1\n"
            "- item 2"
        )
        entry = self.hook._build_history_entry(old_content, "execution", "discovery")
        expected = (
            "## 2026-08-16 \u2014 B4000203 \u2014 history.md entries silently drop Handover\n"
            "**next_agent_role:** execution\n\n"
            "## Handover Note\n"
            "- item 1\n"
            "- item 2"
        )
        self.assertEqual(entry, expected)

    @patch("tools.utils.session_integrity.date")
    def test_buildHistoryEntry_boldLabelHeadingLike_emitsCanonicalHandoverNoteHeader(
        self, mock_date
    ):
        mock_date.today.return_value.isoformat.return_value = "2026-08-16"
        old_content = (
            "# Session State\n\n"
            "**Current Task:** B4000203 \u2014 title\n"
            "**next_agent_role:** planning\n"
            "**Handover to Execution Agent:**\n"
            "- item A\n"
            "- item B"
        )
        entry = self.hook._build_history_entry(old_content, "planning", "execution")
        expected = (
            "## 2026-08-16 \u2014 B4000203 \u2014 title\n"
            "**next_agent_role:** planning\n\n"
            "## Handover Note\n"
            "- item A\n"
            "- item B"
        )
        self.assertEqual(entry, expected)

    @patch("tools.utils.session_integrity.logger.warning")
    @patch("tools.utils.session_integrity.date")
    def test_buildHistoryEntry_fallbackPath_logsWarning(self, mock_date, mock_log_warning):
        mock_date.today.return_value.isoformat.return_value = "2026-08-16"
        old_content = (
            "# Session State\n\n"
            "**Current Task:** B4000203 \u2014 title\n"
            "**next_agent_role:** execution\n"
        )
        entry = self.hook._build_history_entry(old_content, "execution", "discovery")
        expected = (
            "## 2026-08-16 \u2014 B4000203 \u2014 title\n"
            "**next_agent_role:** execution\n\n"
            "## Handover Note\n"
            "**Current Task:** B4000203 \u2014 title\n"
            "**next_agent_role:** execution"
        )
        self.assertEqual(entry, expected)
        mock_log_warning.assert_called_once_with(
            "Could not locate handover section in session.md; falling back to whole-body handover."
        )

    @patch("tools.utils.session_integrity.logger.warning")
    @patch("tools.utils.session_integrity.date")
    def test_buildHistoryEntry_tier1Match_doesNotLogWarning(self, mock_date, mock_log_warning):
        mock_date.today.return_value.isoformat.return_value = "2026-08-16"
        old_content = (
            "# Session State\n\n"
            "**Current Task:** B4000203 \u2014 title\n"
            "**next_agent_role:** execution\n"
            "## Handover Note\n"
            "Body text\n"
        )
        self.hook._build_history_entry(old_content, "execution", "discovery")
        mock_log_warning.assert_not_called()

    def test_buildHistoryEntry_neitherTaskNorHandoverMatch_returnsNone(self):
        old_content = "Just random text without task or handover headers."
        entry = self.hook._build_history_entry(old_content, "execution", "discovery")
        self.assertIsNone(entry)


if __name__ == "__main__":
    unittest.main()
