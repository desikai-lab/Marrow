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

