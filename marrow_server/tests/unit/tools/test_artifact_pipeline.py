import unittest

from tools.artifact_pipeline import DefaultPipeline, PipelineContext
from tools.pipeline_base import PersistPipeline


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
        final_content, applied = await self.dp._apply_updates(
            ctx, "docs/spec.md", group, "existing content"
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
        final_content, applied = await self.dp._apply_updates(
            ctx, "docs/spec.md", group, "old content"
        )
        self.assertEqual(applied, [0])
        self.assertEqual(final_content, "new content")
        self.assertEqual(ctx.results[0]["status"], "success")


class TestDefaultPipelineSignatureGuards(unittest.TestCase):
    def test_readOldContent_signature_hasNoPathParameter(self):
        import inspect
        sig = inspect.signature(DefaultPipeline._read_old_content)
        self.assertNotIn("path", sig.parameters)
