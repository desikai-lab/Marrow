import unittest
from unittest.mock import patch

from services.session_service import load
from utils.exceptions import ArtifactNotFoundError


class TestSessionService(unittest.TestCase):
    @patch("tools.artifacts.read_artifact_logic")
    def test_load_missingSessionFile_raisesValueError(self, mock_read):
        mock_read.side_effect = ArtifactNotFoundError("session", "session.md")
        with self.assertRaises(ValueError) as ctx:
            load("Proj")
        self.assertIn("next_agent_role", str(ctx.exception))

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_nextAgentRolePresent_returnsRoleVerbatim(self, mock_read):
        def side_effect(project, path):
            if path == "session.md":
                return "Phase 7\nnext_agent_role: Planning Agent"
            if path == "spec.md":
                return "SPEC CONTENT"
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        res = load("Proj")
        self.assertEqual(res.phase, 7)
        self.assertEqual(res.agent_role, "Planning Agent")

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_nextAgentRolePresent_overridesPhaseMismatch(self, mock_read):
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
    def test_load_malformedPhaseButNextAgentRolePresent_phaseDefaultsToOne(self, mock_read):
        def side_effect(project, path):
            if path == "session.md":
                return "Phase unknown\nnext_agent_role: Discovery Agent"
            if path == "spec.md":
                return "SPEC CONTENT"
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        res = load("Proj")
        self.assertEqual(res.phase, 1)
        self.assertEqual(res.agent_role, "Discovery Agent")

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_noNextAgentRoleLine_raisesValueError(self, mock_read):
        def side_effect(project, path):
            if path == "session.md":
                return "Phase 12"
            if path == "spec.md":
                return "SPEC"
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        with self.assertRaises(ValueError):
            load("Proj")

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_validProject_returnsSessionTextAndSpec(self, mock_read):
        def side_effect(project, path):
            if path == "session.md":
                return "Phase 12\nnext_agent_role: Execution Agent"
            if path == "spec.md":
                return "SPEC"
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        res = load("Proj")
        self.assertEqual(res.session_text, "Phase 12\nnext_agent_role: Execution Agent")
        self.assertEqual(res.spec, "SPEC")
        self.assertEqual(res.phase, 12)
        self.assertEqual(res.agent_role, "Execution Agent")


if __name__ == "__main__":
    unittest.main()
