import unittest

from tools.artifact_pipeline import DefaultPipeline
from tools.pipeline_dispatcher import PipelineDispatcher
from tools.session_pipeline import SessionPipeline


class TestPipelineDispatcher(unittest.TestCase):
    def setUp(self):
        self.dispatcher = PipelineDispatcher()

    def test_getPipeline_sessionMdPath_returnsSessionPipelineInstance(self):
        pipeline = self.dispatcher.get_pipeline("session.md")
        self.assertIsInstance(pipeline, SessionPipeline)

    def test_getPipeline_anyOtherPath_returnsDefaultPipelineInstance(self):
        for path in ("sessions/history.md", "docs/spec.md", "docs/features/active/F1/plan.md"):
            with self.subTest(path=path):
                pipeline = self.dispatcher.get_pipeline(path)
                self.assertIsInstance(pipeline, DefaultPipeline)

    def test_getPipeline_calledTwiceForSamePath_returnsSameInstance(self):
        first = self.dispatcher.get_pipeline("session.md")
        second = self.dispatcher.get_pipeline("session.md")
        self.assertIs(first, second)
