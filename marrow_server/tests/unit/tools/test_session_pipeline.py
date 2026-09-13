import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from tools.artifact_pipeline import PipelineContext
from tools.session_pipeline import SessionPipeline

from tools.utils.filesystem_utils import resolve_artifact_project_path

GOOD_HEADER = (
    "## SESSION STATE\n**Current Task:** F1 — desc\n**next_agent_role:** Planning Agent\n\n"
)
PROJECT = "TestProject"


class TestExtractNextAgentRole(unittest.TestCase):
    def setUp(self):
        self.sp = SessionPipeline()

    def test_extractNextAgentRole_roleOnlyInSessionStateBlock_returnsBlockValue(self):
        content = (
            "## SESSION STATE\n"
            "**Current Task:** B1\n"
            "**next_agent_role:** Planning Agent\n\n"
            "### Handover Note\n"
            "Quoted elsewhere: **next_agent_role:** Execution Agent\n"
        )
        self.assertEqual(self.sp._extract_next_agent_role(content), "Planning Agent")

    def test_extractNextAgentRole_duplicateRoleLineOutsideBlock_ignoresQuotedOccurrence(self):
        content = (
            "## SESSION STATE\n"
            "**next_agent_role:** Execution Agent\n\n"
            "### Handover Note\n"
            "Previous handover said **next_agent_role:** Discovery Agent, now stale.\n"
        )
        self.assertEqual(self.sp._extract_next_agent_role(content), "Execution Agent")

    def test_extractNextAgentRole_noSessionStateHeading_fallsBackToWholeDocumentScan(self):
        content = "no heading here\n**next_agent_role:** Planning Agent\n"
        with self.assertLogs("tools.session_pipeline", level="WARNING"):
            result = self.sp._extract_next_agent_role(content)
        self.assertEqual(result, "Planning Agent")


class TestHasSessionHeader(unittest.TestCase):
    def setUp(self):
        self.sp = SessionPipeline()

    def test_hasSessionHeader_currentConventionUpperH2_returnsTrue(self):
        content = "## SESSION STATE\n**next_agent_role:** Planning Agent\n"
        self.assertTrue(self.sp._has_session_header(content))

    def test_hasSessionHeader_legacyH1TitleCase_returnsTrue(self):
        content = "# Session State\n**next_agent_role:** Planning Agent\n"
        self.assertTrue(self.sp._has_session_header(content))

    def test_hasSessionHeader_missingNextAgentRole_returnsFalse(self):
        content = "## SESSION STATE\nNo role line here.\n"
        self.assertFalse(self.sp._has_session_header(content))

    def test_hasSessionHeader_noHeadingAtAll_returnsFalse(self):
        content = "**next_agent_role:** Planning Agent\n"
        self.assertFalse(self.sp._has_session_header(content))


class TestBuildHistoryEntryHeadingLevels(unittest.TestCase):
    def setUp(self):
        self.sp = SessionPipeline()

    def test_buildHistoryEntry_hasHandoverNote_nestedHeadingIsH3NotH2(self):
        old_content = (
            "## SESSION STATE\n\n"
            "**Current Task:** B1 — thing\n"
            "**next_agent_role:** execution\n\n"
            "## Handover Note\n"
            "- item 1\n"
        )
        entry = self.sp._build_history_entry(old_content, "execution", "discovery")
        self.assertIn("### Handover Note", entry)
        self.assertNotIn("\n## Handover Note", entry)


class TestSessionPipelineRun(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sp = SessionPipeline()
        self.tmp = tempfile.mkdtemp()
        self.project_path = Path(self.tmp) / PROJECT
        (self.project_path / "artifacts" / "sessions").mkdir(parents=True)
        self.patchers = [patch("config.PROJECTS_ROOT", self.tmp)]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    async def _seed(self, content: str):
        pp = self.project_path / "artifacts" / "session.md"
        pp.write_text(content, encoding="utf-8-sig")

    async def test_run_replaceChunkThenPatchIntermediateStateInvalid_neverRepairsOrAppendsMidRequest(
        self,
    ):
        await self._seed(GOOD_HEADER + "**Focus:** old\n")
        ctx = PipelineContext(
            PROJECT,
            [
                {
                    "path": "session.md",
                    "mode": "replace_file",
                    "content": "**Current Task:** X\nno header",
                },
                {
                    "path": "session.md",
                    "mode": "patch",
                    "old_str": "no header",
                    "content": "## SESSION STATE\n**Current Task:** X\n**next_agent_role:** Execution Agent",
                },
            ],
        )
        group = [(0, ctx.updates[0]), (1, ctx.updates[1])]
        with patch(
            "services.artifact_command_service.save_project_artifacts_logic",
            new_callable=AsyncMock,
        ) as mock_save:
            await self.sp.run(ctx, "session.md", group)
        mock_save.assert_called_once()

    async def test_run_replaceSectionModeChangesRole_appendsHistoryEntry(self):
        await self._seed(
            "## SESSION STATE\n**Current Task:** F1 — desc\n**next_agent_role:** Planning Agent\n\n"
            "### Handover Note\nPlanning done.\n"
        )
        ctx = PipelineContext(
            PROJECT,
            [
                {
                    "path": "session.md",
                    "mode": "replace_section",
                    "section_name": "SESSION STATE",
                    "content": "**Current Task:** F1 — desc\n**next_agent_role:** Execution Agent\n",
                },
            ],
        )
        group = [(0, ctx.updates[0])]
        with patch(
            "services.artifact_command_service.save_project_artifacts_logic",
            new_callable=AsyncMock,
        ) as mock_save:
            await self.sp.run(ctx, "session.md", group)
        mock_save.assert_called_once()
        args, _ = mock_save.call_args
        self.assertEqual(args[1][0]["path"], "sessions/history.md")

    async def test_run_saveContentRaises_historyDecisionNeverRuns(self):
        await self._seed(GOOD_HEADER)
        ctx = PipelineContext(
            PROJECT,
            [
                {
                    "path": "session.md",
                    "mode": "replace_file",
                    "content": GOOD_HEADER.replace("Planning Agent", "Execution Agent"),
                },
            ],
        )
        group = [(0, ctx.updates[0])]
        with (
            patch(
                "common.project_path.ProjectPath.write_async",
                side_effect=OSError("disk full"),
            ),
            patch(
                "services.artifact_command_service.save_project_artifacts_logic",
                new_callable=AsyncMock,
            ) as mock_save,
        ):
            await self.sp.run(ctx, "session.md", group)
        mock_save.assert_not_called()
        self.assertEqual(ctx.results[0]["status"], "error")

    async def test_run_missingHeaderOnReplaceFile_repairsBeforeSave(self):
        await self._seed(GOOD_HEADER + "**Focus:** old\n")
        ctx = PipelineContext(
            PROJECT,
            [
                {
                    "path": "session.md",
                    "mode": "replace_file",
                    "content": "no header at all\n",
                },
            ],
        )
        group = [(0, ctx.updates[0])]
        with patch(
            "services.artifact_command_service.save_project_artifacts_logic",
            new_callable=AsyncMock,
        ):
            await self.sp.run(ctx, "session.md", group)
        pp = self.project_path / "artifacts" / "session.md"
        persisted = pp.read_text(encoding="utf-8-sig")
        self.assertIn("SESSION STATE", persisted)

    async def test_applyUpdates_allUpdatesFail_returnsEmptyAppliedList(self):
        ctx = PipelineContext(
            PROJECT,
            [
                {
                    "path": "session.md",
                    "mode": "patch",
                    "old_str": "not present anywhere",
                    "content": "x",
                },
            ],
        )
        group = [(0, ctx.updates[0])]
        project_path = resolve_artifact_project_path(PROJECT, "session.md")
        final_content, applied = await self.sp._apply_updates(
            ctx, project_path, group, GOOD_HEADER
        )
        self.assertEqual(applied, [])
        self.assertEqual(ctx.results[0]["status"], "error")


class TestExtractHandoverBody(unittest.TestCase):
    def setUp(self):
        self.sp = SessionPipeline()

    def test_extractHandoverBody_canonicalHeading_returnsBodyAndFalse(self):
        content = (
            "## SESSION STATE\n\n"
            "**Current Task:** B1 — test\n"
            "**next_agent_role:** execution\n\n"
            "## Handover Note\n"
            "Line 1\n"
            "Line 2\n\n"
            "## Next Section\n"
        )
        body, used_fallback = self.sp._extract_handover_body(content)
        self.assertEqual(body, "Line 1\nLine 2")
        self.assertFalse(used_fallback)

    def test_extractHandoverBody_boldLabelHeadingLike_returnsBodyAndFalse(self):
        content = (
            "## SESSION STATE\n\n"
            "**Current Task:** B1\n"
            "**next_agent_role:** execution\n\n"
            "**Handover Note:**\n"
            "Line A\n"
            "Line B\n"
        )
        body, used_fallback = self.sp._extract_handover_body(content)
        self.assertEqual(body, "Line A\nLine B")
        self.assertFalse(used_fallback)

    def test_extractHandoverBody_incidentalMention_prefersTier1OverTier2(self):
        content = (
            "## SESSION STATE\n\n"
            "**Task status:** DONE, no handover issues here.\n\n"
            "## Handover Note\n"
            "Real handover content\n"
        )
        body, used_fallback = self.sp._extract_handover_body(content)
        self.assertEqual(body, "Real handover content")
        self.assertFalse(used_fallback)

    def test_extractHandoverBody_incidentalMentionOnly_usesTier2Line(self):
        content = (
            "## SESSION STATE\n\n"
            "**Current Task:** B1\n"
            "Handover details start here:\n"
            "Line X\n"
            "Line Y\n"
        )
        body, used_fallback = self.sp._extract_handover_body(content)
        self.assertEqual(body, "Line X\nLine Y")
        self.assertFalse(used_fallback)

    def test_extractHandoverBody_noHandoverMentionAtAll_returnsFallbackBodyAndTrue(self):
        content = "## SESSION STATE\n\n**Current Task:** B1\n**next_agent_role:** discovery\n\nBody content\n"
        body, used_fallback = self.sp._extract_handover_body(content)
        self.assertEqual(
            body, "**Current Task:** B1\n**next_agent_role:** discovery\n\nBody content"
        )
        self.assertTrue(used_fallback)


class TestBuildHistoryEntry(unittest.TestCase):
    def setUp(self):
        self.sp = SessionPipeline()

    def test_buildHistoryEntry_canonicalHeading_preservesOriginalFormattingByteIdentical(self):
        old_content = (
            "## SESSION STATE\n\n"
            "**Current Task:** B1 — test task\n"
            "**next_agent_role:** execution\n\n"
            "## Handover Note\n"
            "Some handover body\n"
        )
        entry = self.sp._build_history_entry(old_content, "execution", "discovery")
        self.assertIsNotNone(entry)
        self.assertIn("## ", entry)
        self.assertIn("B1 — test task", entry)
        self.assertIn("**next_agent_role:** execution", entry)
        self.assertIn("### Handover Note\nSome handover body", entry)

    def test_buildHistoryEntry_boldLabelHeadingLike_emitsCanonicalHandoverNoteHeader(self):
        old_content = (
            "# Session State\n\n"
            "**Current Task:** B1 — test task\n"
            "**next_agent_role:** execution\n\n"
            "**Handover Note:**\n"
            "Line 1\n"
        )
        entry = self.sp._build_history_entry(old_content, "execution", "discovery")
        self.assertIsNotNone(entry)
        self.assertIn("### Handover Note\nLine 1", entry)

    def test_buildHistoryEntry_fallbackPath_logsWarning(self):
        old_content = (
            "## SESSION STATE\n\n**Current Task:** B1 — test task\n**next_agent_role:** execution\n"
        )
        with self.assertLogs("tools.session_pipeline", level="WARNING") as cm:
            entry = self.sp._build_history_entry(old_content, "execution", "discovery")
        self.assertIsNotNone(entry)
        self.assertTrue(any("falling back to whole-body handover" in msg for msg in cm.output))


class TestSessionPipelineSignatureGuards(unittest.TestCase):
    def test_readOldContent_signature_hasNoPathParameter(self):
        import inspect
        sig = inspect.signature(SessionPipeline._read_old_content)
        self.assertNotIn("path", sig.parameters)


class TestSessionPipelineBackupTiming(unittest.IsolatedAsyncioTestCase):
    async def test_run_allUpdatesFailToApply_noBackupTaken(self):
        sp = SessionPipeline()
        ctx = PipelineContext(
            "TestProject",
            [
                {
                    "path": "session.md",
                    "mode": "patch",
                    "old_str": "not present anywhere",
                    "content": "x",
                },
            ],
        )
        group = [(0, ctx.updates[0])]
        with (
            patch("tools.session_pipeline.create_artifact_backup") as mock_backup,
            patch(
                "common.project_path.ProjectPath.exists_async", return_value=True
            ),
            patch(
                "common.project_path.ProjectPath.read_async",
                return_value="## SESSION STATE\n**next_agent_role:** Planning Agent\n",
            ),
        ):
            await sp.run(ctx, "session.md", group)
        mock_backup.assert_not_called()

    async def test_run_saveContentRaises_backupWasTakenBeforeFailedWrite(self):
        sp = SessionPipeline()
        ctx = PipelineContext(
            "TestProject",
            [
                {
                    "path": "session.md",
                    "mode": "replace_file",
                    "content": "## SESSION STATE\n**next_agent_role:** Execution Agent\n",
                },
            ],
        )
        group = [(0, ctx.updates[0])]
        with (
            patch("tools.session_pipeline.create_artifact_backup") as mock_backup,
            patch(
                "common.project_path.ProjectPath.exists_async", return_value=True
            ),
            patch(
                "common.project_path.ProjectPath.read_async",
                return_value="## SESSION STATE\n**next_agent_role:** Planning Agent\n",
            ),
            patch(
                "common.project_path.ProjectPath.write_async",
                side_effect=OSError("disk full"),
            ),
        ):
            await sp.run(ctx, "session.md", group)
        # Accepted residual: backup DOES fire here, since we were genuinely
        # committed to writing -- this locks in that documented trade-off.
        mock_backup.assert_called_once()
        self.assertEqual(ctx.results[0]["status"], "error")
