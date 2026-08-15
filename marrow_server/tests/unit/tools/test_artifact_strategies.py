import unittest

from models import ReadRequest


class TestReadRequestModeDefault(unittest.TestCase):
    def test_readRequest_modeOmitted_defaultsToPaged(self):
        req = ReadRequest(path="spec.md")
        self.assertEqual(req.mode, "paged")

    def test_readRequest_modePaged_isAcceptedLiteral(self):
        req = ReadRequest(path="spec.md", mode="paged")
        self.assertEqual(req.mode, "paged")

    def test_readArtifactLogic_defaultMode_isPaged(self):
        import inspect
        from tools.artifacts import read_artifact_logic

        sig = inspect.signature(read_artifact_logic)
        self.assertEqual(sig.parameters["mode"].default, "paged")


class TestFullReadStrategyStrict(unittest.TestCase):
    def setUp(self):
        import os
        import tempfile

        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "big.md")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("x" * 12000)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_FullReadStrategy_ContentExceedsDefaultMaxChars_ReturnsCompleteContent(self):
        from tools.utils.artifact_strategies import FullReadStrategy

        result = FullReadStrategy().read(self.path)
        self.assertEqual(len(result), 12000)
        self.assertNotIn("truncated", result)

    def test_FullReadStrategy_SkipCharsAndDirectionProvided_AreIgnored(self):
        from tools.utils.artifact_strategies import FullReadStrategy

        result = FullReadStrategy().read(self.path, skip_chars=500, direction="end")
        self.assertEqual(len(result), 12000)
        self.assertTrue(result.startswith("x"))


