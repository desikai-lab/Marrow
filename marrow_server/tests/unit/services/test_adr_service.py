import unittest
from unittest.mock import patch

from services.adr_service import _extract_adr_summary, _parse_foundational_adr_paths, load
from utils.exceptions import ArtifactNotFoundError


class TestAdrService(unittest.TestCase):
    _MINIMAL_INDEX = (
        "## Foundational ADRs 🔴\n"
        "| ID | Title | Status |\n"
        "|---|---|---|\n"
        "| 0007 | [A](adr/0007-a.md) | Accepted |\n"
        "| 0008 | [B](adr/0008-b.md) | Accepted |\n"
    )

    _MOCK_YAML = """
roles:
  planning:
    guideline: docs/manuals/guidelines/planning.md
    adrs: ["0007", "0008"]
    playbooks: []
"""

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_validProject_returnsJoinedAdrSummaries(self, mock_read):
        def side_effect(project, path):
            if path == "docs/decisions/0000-index.md":
                return self._MINIMAL_INDEX
            if path == "docs/decisions/adr/0007-a.md":
                return "# A\n## Summary\nSummary A"
            if path == "docs/decisions/adr/0008-b.md":
                return "# B\n## Summary\nSummary B"
            if path == "docs/manuals/role_profiles.yaml":
                return self._MOCK_YAML
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        res = load("Proj", "planning")
        self.assertIn("# A\n**Source:** `docs/decisions/adr/0007-a.md`\n\nSummary A", res)
        self.assertIn("# B\n**Source:** `docs/decisions/adr/0008-b.md`\n\nSummary B", res)

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_missingAdrIndex_returnsEmptyString(self, mock_read):
        mock_read.side_effect = ArtifactNotFoundError("file", "docs/decisions/0000-index.md")
        res = load("Proj", "planning")
        self.assertEqual(res, "")

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_missingIndividualAdrFile_skipsAndContinues(self, mock_read):
        def side_effect(project, path):
            if path == "docs/decisions/0000-index.md":
                return self._MINIMAL_INDEX
            if path == "docs/decisions/adr/0007-a.md":
                return "# A\n## Summary\nSummary A"
            if path == "docs/decisions/adr/0008-b.md":
                raise ArtifactNotFoundError("file", path)
            if path == "docs/manuals/role_profiles.yaml":
                return self._MOCK_YAML
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        with self.assertLogs("services.adr_service", level="WARNING") as log:
            res = load("Proj", "planning")
        self.assertIn("# A", res)
        self.assertNotIn("# B", res)
        self.assertTrue(any("0008-b.md" in m for m in log.output))

    @patch("tools.artifacts.read_artifact_logic")
    def test_load_emptyAdrsInProfile_returnsEmptyString(self, mock_read):
        empty_yaml = """
roles:
  planning:
    guideline: docs/manuals/guidelines/planning.md
    adrs: []
    playbooks: []
"""

        def side_effect(project, path):
            if path == "docs/decisions/0000-index.md":
                return self._MINIMAL_INDEX
            if path == "docs/manuals/role_profiles.yaml":
                return empty_yaml
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        res = load("Proj", "planning")
        self.assertEqual(res, "")

    def test_parseFoundationalAdrPaths_noRoleFilter_returnsAllPaths(self):
        result = _parse_foundational_adr_paths(self._MINIMAL_INDEX)
        self.assertEqual(
            result,
            [
                "docs/decisions/adr/0007-a.md",
                "docs/decisions/adr/0008-b.md",
            ],
        )

    def test_parseFoundationalAdrPaths_missingSectionHeader_returnsEmptyList(self):
        result = _parse_foundational_adr_paths("## Contextual ADRs\n...")
        self.assertEqual(result, [])

    def test_extractAdrSummary_summaryPresent_prependsTitleAndSource(self):
        adr_text = "# ADR-07: Pipeline Standard\n## Summary\nThis is the summary content."
        result = _extract_adr_summary(adr_text, "docs/decisions/adr/0007-pipeline-standard.md")
        expected = (
            "# ADR-07: Pipeline Standard\n"
            "**Source:** `docs/decisions/adr/0007-pipeline-standard.md`\n\n"
            "This is the summary content."
        )
        self.assertEqual(result, expected)

    def test_extractAdrSummary_summaryMissing_returnsFullText(self):
        adr_text = "# ADR-08: No Summary\nContext here."
        result = _extract_adr_summary(adr_text, "docs/decisions/adr/0008-no-summary.md")
        self.assertEqual(result, adr_text)
