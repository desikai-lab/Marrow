import unittest
from unittest.mock import patch

from tools.artifact_pipeline import DefaultPipeline, PipelineContext
from tools.pipeline_base import PersistPipeline
from tools.utils.filesystem_utils import resolve_artifact_project_path


class TestPersistPipelineInterface(unittest.TestCase):
    def test_defaultPipeline_isPersistPipelineSubclass(self):
        self.assertTrue(issubclass(DefaultPipeline, PersistPipeline))


class TestDefaultPipelineApplyUpdates(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.dp = DefaultPipeline()

    async def test_applyUpdates_allUpdatesFail_returnsEmptyAppliedList(self):
        ctx = PipelineContext(
            "TestProject",
            [
                {
                    "path": "docs/spec.md",
                    "mode": "patch",
                    "old_str": "not present anywhere",
                    "content": "x",
                },
            ],
        )
        group = [(0, ctx.updates[0])]
        project_path = resolve_artifact_project_path("TestProject", "docs/spec.md")
        final_content, applied = await self.dp._apply_updates(
            ctx, project_path, group, "existing content"
        )
        self.assertEqual(applied, [])
        self.assertEqual(ctx.results[0]["status"], "error")

    async def test_applyUpdates_replaceFileSucceeds_returnsAppliedIndexAndNewContent(self):
        ctx = PipelineContext(
            "TestProject",
            [
                {"path": "docs/spec.md", "mode": "replace_file", "content": "new content"},
            ],
        )
        group = [(0, ctx.updates[0])]
        project_path = resolve_artifact_project_path("TestProject", "docs/spec.md")
        final_content, applied = await self.dp._apply_updates(
            ctx, project_path, group, "old content"
        )
        self.assertEqual(applied, [0])
        self.assertEqual(final_content, "new content")
        self.assertEqual(ctx.results[0]["status"], "success")

    async def test_applyUpdates_success_resultPathIsRelativePathNotRawArg(self):
        ctx = PipelineContext(
            "TestProject",
            [
                {"path": "Docs/Spec.md", "mode": "replace_file", "content": "x"},
            ],
        )
        project_path = resolve_artifact_project_path("TestProject", "Docs/Spec.md")
        group = [(0, ctx.updates[0])]
        await self.dp._apply_updates(ctx, project_path, group, "old")
        self.assertEqual(ctx.results[0]["path"], project_path.relative_path)

    async def test_run_resolveFails_resultReportsRawPathNotCrash(self):
        dp = DefaultPipeline()
        ctx = PipelineContext(
            "TestProject",
            [
                {"path": "../escape.md", "mode": "replace_file", "content": "x"},
            ],
        )
        group = [(0, ctx.updates[0])]
        with patch(
            "tools.artifact_pipeline.resolve_artifact_project_path",
            side_effect=ValueError("bad path"),
        ):
            await dp.run(ctx, "../escape.md", group)
        self.assertEqual(ctx.results[0]["status"], "error")
        self.assertEqual(ctx.results[0]["path"], "../escape.md")  # raw fallback, not a crash


class TestDefaultPipelineSignatureGuards(unittest.TestCase):
    def test_readOldContent_signature_hasNoPathParameter(self):
        import inspect
        sig = inspect.signature(DefaultPipeline._read_old_content)
        self.assertNotIn("path", sig.parameters)


class TestDefaultPipelineBackupTiming(unittest.IsolatedAsyncioTestCase):
    async def test_run_allUpdatesFailToApply_noBackupTaken(self):
        dp = DefaultPipeline()
        ctx = PipelineContext(
            "TestProject",
            [
                {
                    "path": "docs/spec.md",
                    "mode": "patch",
                    "old_str": "not present anywhere",
                    "content": "x",
                },
            ],
        )
        group = [(0, ctx.updates[0])]
        with (
            patch("tools.artifact_pipeline.create_artifact_backup") as mock_backup,
            patch(
                "common.project_path.ProjectPath.exists_async", return_value=True
            ),
            patch(
                "common.project_path.ProjectPath.read_async",
                return_value="existing content",
            ),
        ):
            await dp.run(ctx, "docs/spec.md", group)
        mock_backup.assert_not_called()

    async def test_run_saveContentRaises_backupWasTakenBeforeFailedWrite(self):
        dp = DefaultPipeline()
        ctx = PipelineContext(
            "TestProject",
            [
                {
                    "path": "docs/spec.md",
                    "mode": "replace_file",
                    "content": "new content",
                },
            ],
        )
        group = [(0, ctx.updates[0])]
        with (
            patch("tools.artifact_pipeline.create_artifact_backup") as mock_backup,
            patch(
                "common.project_path.ProjectPath.exists_async", return_value=True
            ),
            patch(
                "common.project_path.ProjectPath.read_async",
                return_value="old content",
            ),
            patch(
                "common.project_path.ProjectPath.write_async",
                side_effect=OSError("disk full"),
            ),
        ):
            await dp.run(ctx, "docs/spec.md", group)
        # Accepted residual: backup DOES fire here, since we were genuinely
        # committed to writing -- this locks in that documented trade-off.
        mock_backup.assert_called_once()
        self.assertEqual(ctx.results[0]["status"], "error")
