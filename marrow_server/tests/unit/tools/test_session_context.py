import unittest
from unittest.mock import patch, MagicMock
from tools.session_context import _parse_phase, _select_agent_role, get_session_context_logic
from utils.exceptions import ArtifactNotFoundError

class TestSessionContext(unittest.TestCase):

    def test_parse_phase_valid_string_returns_phase_number(self):
        self.assertEqual(_parse_phase("Current Phase: 5"), 5)
        self.assertEqual(_parse_phase("We are at phase 12 now"), 12)

    def test_parse_phase_case_insensitive_string_returns_phase_number(self):
        self.assertEqual(_parse_phase("PHASE 3"), 3)
        self.assertEqual(_parse_phase("phase 8 ACTIVE"), 8)

    def test_parse_phase_empty_string_returns_one(self):
        self.assertEqual(_parse_phase(""), 1)
        self.assertEqual(_parse_phase("No digits here"), 1)

    def test_parse_phase_malformed_string_returns_one(self):
        self.assertEqual(_parse_phase("Phase: unknown"), 1)
        self.assertEqual(_parse_phase("Phase -5"), 1)  # regex \d only matches positive

    def test_select_agent_role_phase_1_returns_discovery_agent(self):
        self.assertEqual(_select_agent_role(1), "Discovery Agent")

    def test_select_agent_role_phase_6_returns_architecture_agent(self):
        self.assertEqual(_select_agent_role(6), "Architecture Agent")

    def test_select_agent_role_phase_7_returns_planning_agent(self):
        self.assertEqual(_select_agent_role(7), "Planning Agent")
        self.assertEqual(_select_agent_role(11), "Planning Agent")

    def test_select_agent_role_phase_12_returns_execution_agent(self):
        self.assertEqual(_select_agent_role(12), "Execution Agent")
        self.assertEqual(_select_agent_role(99), "Execution Agent")

    @patch("tools.session_context.read_artifact_logic")
    def test_get_session_context_logic_valid_project_returns_context_string(self, mock_read):
        def side_effect(project, path):
            if path == "session.md":
                return "Phase 8"
            if path == "docs/manuals/guidelines/core.md":
                return "CORE CONTENT"
            if path == "docs/manuals/guidelines/planning.md":
                return "PLANNING CONTENT"
            return "ERROR"
            
        mock_read.side_effect = side_effect
        
        result = get_session_context_logic("TestProj")
        
        self.assertIn("=== YOUR ROLE: Planning Agent ===", result)
        self.assertIn("Phase 8", result)
        self.assertIn("CORE CONTENT", result)
        self.assertIn("PLANNING CONTENT", result)
        self.assertIn("=== PHASE GUIDELINES (Planning Agent) ===", result)

    @patch("tools.session_context.read_artifact_logic")
    def test_get_session_context_logic_missing_session_returns_discovery_context(self, mock_read):
        def side_effect(project, path):
            if path == "session.md":
                raise ArtifactNotFoundError("session", "session.md")
            if path == "docs/manuals/guidelines/core.md":
                return "CORE CONTENT"
            if path == "docs/manuals/guidelines/discovery.md":
                return "DISCOVERY CONTENT"
            return "ERROR"
            
        mock_read.side_effect = side_effect
        
        # Should default to phase 1 -> Discovery Agent
        result = get_session_context_logic("TestProj")
        
        self.assertIn("=== SESSION STATE ===\n\n", result)
        self.assertIn("DISCOVERY CONTENT", result)
        self.assertIn("=== PHASE GUIDELINES (Discovery Agent) ===", result)

    @patch("tools.session_context.read_artifact_logic")
    def test_get_session_context_logic_missing_guidelines_raises_artifact_not_found_error(self, mock_read):
        def side_effect(project, path):
            if path == "session.md":
                return "Phase 12"
            if path == "docs/manuals/guidelines/core.md":
                raise ArtifactNotFoundError("core", path)
            return "ERROR"
            
        mock_read.side_effect = side_effect
        
        with self.assertRaises(ArtifactNotFoundError):
            get_session_context_logic("TestProj")

if __name__ == "__main__":
    unittest.main()

