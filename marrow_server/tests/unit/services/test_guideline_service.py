import unittest
from unittest.mock import patch

from services.guideline_service import GuidelineBundle, load
from utils.exceptions import ArtifactNotFoundError


class TestGuidelineService(unittest.TestCase):
    _MOCK_YAML = """
roles:
  planning:
    guideline: docs/manuals/guidelines/planning.md
    adrs: []
    playbooks: []
"""

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_validRole_returnsGuidelineBundleWithCoreAndPhaseText(self, mock_read):
        def side_effect(project, path):
            if path == "docs/manuals/guidelines/core.md":
                return "CORE TEXT"
            if path == "docs/manuals/role_profiles.yaml":
                return self._MOCK_YAML
            if path == "docs/manuals/guidelines/planning.md":
                return "PLANNING TEXT"
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        res = load("Proj", "planning")
        self.assertIsInstance(res, GuidelineBundle)
        self.assertEqual(res.core_text, "CORE TEXT")
        self.assertEqual(res.phase_text, "PLANNING TEXT")

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_missingYaml_returnsErrorString(self, mock_read):
        def side_effect(project, path):
            if path == "docs/manuals/guidelines/core.md":
                return "CORE TEXT"
            if path == "docs/manuals/role_profiles.yaml":
                raise ArtifactNotFoundError("file", path)
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        res = load("Proj", "planning")
        self.assertIsInstance(res, str)
        self.assertIn("role_profiles.yaml not found", res)

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_unknownRole_returnsErrorString(self, mock_read):
        def side_effect(project, path):
            if path == "docs/manuals/guidelines/core.md":
                return "CORE TEXT"
            if path == "docs/manuals/role_profiles.yaml":
                return self._MOCK_YAML
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        res = load("Proj", "unknown_role")
        self.assertIsInstance(res, str)
        self.assertIn("Unknown role 'unknown_role'", res)

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_missingGuidelineFile_returnsErrorString(self, mock_read):
        def side_effect(project, path):
            if path == "docs/manuals/guidelines/core.md":
                return "CORE TEXT"
            if path == "docs/manuals/role_profiles.yaml":
                return self._MOCK_YAML
            if path == "docs/manuals/guidelines/planning.md":
                raise ArtifactNotFoundError("file", path)
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        res = load("Proj", "planning")
        self.assertIsInstance(res, str)
        self.assertIn("guideline file not found", res)

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_agentRoleNormalized_resolvesCorrectProfile(self, mock_read):
        def side_effect(project, path):
            if path == "docs/manuals/guidelines/core.md":
                return "CORE TEXT"
            if path == "docs/manuals/role_profiles.yaml":
                return self._MOCK_YAML
            if path == "docs/manuals/guidelines/planning.md":
                return "PLANNING TEXT"
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        res = load("Proj", "Planning Agent")
        self.assertIsInstance(res, GuidelineBundle)
        self.assertEqual(res.phase_text, "PLANNING TEXT")
