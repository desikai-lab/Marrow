import unittest
from unittest.mock import patch

from services.session_service import load
from utils.exceptions import ArtifactNotFoundError


class TestSessionService(unittest.TestCase):
    @patch("tools.artifacts.read_artifact_logic")
    def test_load_missingSessionFile_returnsEmptyContextWithDiscoveryRole(self, mock_read):
        mock_read.side_effect = ArtifactNotFoundError("session", "session.md")
        res = load("Proj")
        self.assertEqual(res.session_text, "")
        self.assertEqual(res.spec, "")
        self.assertEqual(res.phase, 1)
        self.assertEqual(res.agent_role, "Discovery Agent")

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_validSessionWithPhase7_returnsPlanningAgentRole(self, mock_read):
        def side_effect(project, path):
            if path == "session.md":
                return "Phase 7"
            if path == "spec.md":
                return "SPEC CONTENT"
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        res = load("Proj")
        self.assertEqual(res.session_text, "Phase 7")
        self.assertEqual(res.spec, "SPEC CONTENT")
        self.assertEqual(res.phase, 7)
        self.assertEqual(res.agent_role, "Planning Agent")

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_nextAgentRolePresent_overridesPhaseDetection(self, mock_read):
        def side_effect(project, path):
            if path == "session.md":
                return "Phase 7\nnext_agent_role: execution"
            if path == "spec.md":
                return "SPEC CONTENT"
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        res = load("Proj")
        self.assertEqual(res.phase, 7)
        self.assertEqual(res.agent_role, "execution")

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_malformedPhase_defaultsToDiscoveryRole(self, mock_read):
        def side_effect(project, path):
            if path == "session.md":
                return "Phase unknown"
            if path == "spec.md":
                return "SPEC CONTENT"
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        res = load("Proj")
        self.assertEqual(res.phase, 1)
        self.assertEqual(res.agent_role, "Discovery Agent")

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_validProject_returnsSessionTextAndSpec(self, mock_read):
        def side_effect(project, path):
            if path == "session.md":
                return "Phase 12"
            if path == "spec.md":
                return "SPEC"
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        res = load("Proj")
        self.assertEqual(res.session_text, "Phase 12")
        self.assertEqual(res.spec, "SPEC")
        self.assertEqual(res.phase, 12)
        self.assertEqual(res.agent_role, "Execution Agent")
