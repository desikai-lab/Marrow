import unittest
from unittest.mock import patch

from services.session_service import _parse_phase
from tools.session_context import get_session_context_logic
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


    @patch("tools.artifacts.read_artifact_logic")
    def test_get_session_context_logic_valid_project_returns_context_string(self, mock_read):
        def side_effect(project, path):
            if path == "session.md":
                return "Phase 8\nnext_agent_role: Planning Agent"
            if path == "docs/manuals/role_profiles.yaml":
                return "roles:\n  planning:\n    guideline: docs/manuals/guidelines/planning.md\n    adrs: []\n    playbooks: []"
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

    @patch("tools.artifacts.read_artifact_logic")
    def test_get_session_context_logic_missing_session_raises_value_error(self, mock_read):
        def side_effect(project, path):
            if path == "session.md":
                raise ArtifactNotFoundError("session", "session.md")
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect

        with self.assertRaises(ValueError):
            get_session_context_logic("TestProj")

    @patch("tools.artifacts.read_artifact_logic")
    def test_get_session_context_logic_missing_guidelines_raises_artifact_not_found_error(
        self, mock_read
    ):
        def side_effect(project, path):
            if path == "session.md":
                return "Phase 12\nnext_agent_role: Execution Agent"
            if path == "docs/manuals/role_profiles.yaml":
                return "roles:\n  execution:\n    guideline: docs/manuals/guidelines/execution.md\n    adrs: []\n    playbooks: []"
            if path == "docs/manuals/guidelines/core.md":
                raise ArtifactNotFoundError("core", path)
            return "ERROR"

        mock_read.side_effect = side_effect

        with self.assertRaises(ArtifactNotFoundError):
            get_session_context_logic("TestProj")


class TestParseFounationalAdrPaths(unittest.TestCase):
    def test_valid_index_returns_correct_paths(self):
        index_text = (
            "## Foundational ADRs 🔴\n"
            "| ID | Title | Status |\n"
            "|---|---|---|\n"
            "| 0007 | [Pipeline Standard](adr/0007-pipeline-standard.md) | Accepted |\n"
            "| 0008 | [Three-Tier Arch](adr/0008-three-tier-arch.md) | Accepted |\n"
            "| 0010 | [Auto-unblock](adr/0010-auto-unblock.md) | Accepted |\n"
            "\n## Contextual ADRs 🟢\n"
            "| 0001 | [Entry Point Split](adr/0001-entry-point-split.md) | Accepted |\n"
        )
        from services.adr_service import _parse_foundational_adr_paths

        result = _parse_foundational_adr_paths(index_text)
        self.assertEqual(
            result,
            [
                "docs/decisions/adr/0007-pipeline-standard.md",
                "docs/decisions/adr/0008-three-tier-arch.md",
                "docs/decisions/adr/0010-auto-unblock.md",
            ],
        )

    def test_missing_section_returns_empty_list(self):
        from services.adr_service import _parse_foundational_adr_paths

        result = _parse_foundational_adr_paths("## Some Other Section\nno links here")
        self.assertEqual(result, [])


class TestGetSessionContextLogicAdrInjection(unittest.TestCase):
    _MINIMAL_INDEX = (
        "## Foundational ADRs 🔴\n"
        "| 0007 | [A](adr/0007-a.md) | Accepted |\n"
        "| 0008 | [B](adr/0008-b.md) | Accepted |\n"
        "\n## Contextual ADRs 🟢\n"
    )

    def _base_side_effect(self, project, path):
        if path == "session.md":
            return "Phase 8\nnext_agent_role: planning"
        if path == "spec.md":
            return "SPEC"
        if path == "docs/manuals/guidelines/core.md":
            return "CORE"
        if path == "docs/manuals/guidelines/planning.md":
            return "PLAN"
        if path == "docs/manuals/role_profiles.yaml":
            return """
roles:
  planning:
    guideline: docs/manuals/guidelines/planning.md
    adrs: ["0007", "0008"]
    playbooks: []
  discovery:
    guideline: docs/manuals/guidelines/discovery.md
    adrs: ["0007", "0008"]
    playbooks: []
  execution:
    guideline: docs/manuals/guidelines/execution.md
    adrs: ["0007", "0008"]
    playbooks: []
"""
        return None

    @patch("tools.artifacts.read_artifact_logic")
    def test_all_adrs_present_returns_bundle_with_foundational_section(self, mock_read):
        def side_effect(project, path):
            base = self._base_side_effect(project, path)
            if base is not None:
                return base
            if path == "docs/decisions/0000-index.md":
                return self._MINIMAL_INDEX
            if path == "docs/decisions/adr/0007-a.md":
                return "ADR BODY A"
            if path == "docs/decisions/adr/0008-b.md":
                return "ADR BODY B"
            return "ERROR"

        mock_read.side_effect = side_effect
        result = get_session_context_logic("TestProj")
        self.assertIn("=== FOUNDATIONAL DECISIONS ===", result)
        self.assertIn("ADR BODY A", result)
        self.assertIn("ADR BODY B", result)

    @patch("tools.artifacts.read_artifact_logic")
    def test_one_adr_missing_warns_and_continues(self, mock_read):
        def side_effect(project, path):
            base = self._base_side_effect(project, path)
            if base is not None:
                return base
            if path == "docs/decisions/0000-index.md":
                return self._MINIMAL_INDEX
            if path == "docs/decisions/adr/0007-a.md":
                return "ADR BODY A"
            if path == "docs/decisions/adr/0008-b.md":
                raise ArtifactNotFoundError("adr", path)
            return "ERROR"

        mock_read.side_effect = side_effect
        with self.assertLogs("services.adr_service", level="WARNING") as log:
            result = get_session_context_logic("TestProj")
        self.assertIn("ADR BODY A", result)
        self.assertTrue(any("0008-b.md" in m for m in log.output))

    @patch("tools.artifacts.read_artifact_logic")
    def test_index_missing_warns_and_returns_empty_adr_section(self, mock_read):
        def side_effect(project, path):
            base = self._base_side_effect(project, path)
            if base is not None:
                return base
            if path == "docs/decisions/0000-index.md":
                raise ArtifactNotFoundError("index", path)
            return "ERROR"

        mock_read.side_effect = side_effect
        with self.assertLogs("services.adr_service", level="WARNING") as log:
            result = get_session_context_logic("TestProj")
        self.assertIn("=== FOUNDATIONAL DECISIONS ===", result)
        self.assertTrue(any("0000-index.md" in m for m in log.output))


class TestExtractAdrSummary(unittest.TestCase):
    def test_summary_present_prepends_title_and_source(self):
        from services.adr_service import _extract_adr_summary

        adr_text = (
            "# ADR-07: Pipeline Standard\n"
            "**Date:** 2026-03-21\n\n"
            "## Summary\n"
            "This is the summary content.\n\n"
            "## Context\n"
            "Context here."
        )
        result = _extract_adr_summary(adr_text, "docs/decisions/adr/0007-pipeline-standard.md")
        expected = (
            "# ADR-07: Pipeline Standard\n"
            "**Source:** `docs/decisions/adr/0007-pipeline-standard.md`\n\n"
            "This is the summary content."
        )
        self.assertEqual(result, expected)

    def test_summary_missing_returns_full_text(self):
        from services.adr_service import _extract_adr_summary

        adr_text = "# ADR-08: No Summary\n**Date:** 2026-03-21\n\n## Context\nContext here."
        result = _extract_adr_summary(adr_text, "docs/decisions/adr/0008-no-summary.md")
        self.assertEqual(result, adr_text)


class TestParseFoundationalAdrPathsExtended(unittest.TestCase):
    def test_parseFoundationalAdrPaths_noRoleFilter_returnsAllPaths(self):
        index_text = (
            "## Foundational ADRs 🔴\n"
            "| ID | Title | Status | Roles |\n"
            "|----|-------|--------|-------|\n"
            "| 0007 | [Pipeline Standard](adr/0007-pipeline-standard.md) | Accepted | all |\n"
            "| 0019 | [Streamable HTTP Transport](adr/0019-streamable-http.md) | Accepted | execution |\n"
            "| 0034 | [Product Name](adr/0034-product-name-marrow.md) | Accepted | discovery |\n"
        )
        from services.adr_service import _parse_foundational_adr_paths

        res = _parse_foundational_adr_paths(index_text)
        self.assertEqual(len(res), 3)
        self.assertIn("docs/decisions/adr/0007-pipeline-standard.md", res)
        self.assertIn("docs/decisions/adr/0019-streamable-http.md", res)
        self.assertIn("docs/decisions/adr/0034-product-name-marrow.md", res)

    def test_parseFoundationalAdrPaths_roleExecution_returnsFilteredPaths(self):
        index_text = (
            "## Foundational ADRs 🔴\n"
            "| ID | Title | Status | Roles |\n"
            "|----|-------|--------|-------|\n"
            "| 0007 | [Pipeline Standard](adr/0007-pipeline-standard.md) | Accepted | all |\n"
            "| 0019 | [Streamable HTTP Transport](adr/0019-streamable-http.md) | Accepted | execution |\n"
            "| 0034 | [Product Name](adr/0034-product-name-marrow.md) | Accepted | discovery |\n"
        )
        from services.adr_service import _parse_foundational_adr_paths

        res = _parse_foundational_adr_paths(index_text, "execution")
        self.assertEqual(len(res), 2)
        self.assertIn("docs/decisions/adr/0007-pipeline-standard.md", res)
        self.assertIn("docs/decisions/adr/0019-streamable-http.md", res)
        self.assertNotIn("docs/decisions/adr/0034-product-name-marrow.md", res)

    def test_parseFoundationalAdrPaths_roleDiscovery_returnsFilteredPaths(self):
        index_text = (
            "## Foundational ADRs 🔴\n"
            "| ID | Title | Status | Roles |\n"
            "|----|-------|--------|-------|\n"
            "| 0007 | [Pipeline Standard](adr/0007-pipeline-standard.md) | Accepted | all |\n"
            "| 0019 | [Streamable HTTP Transport](adr/0019-streamable-http.md) | Accepted | execution |\n"
            "| 0034 | [Product Name](adr/0034-product-name-marrow.md) | Accepted | discovery |\n"
        )
        from services.adr_service import _parse_foundational_adr_paths

        res = _parse_foundational_adr_paths(index_text, "discovery")
        self.assertEqual(len(res), 2)
        self.assertIn("docs/decisions/adr/0007-pipeline-standard.md", res)
        self.assertNotIn("docs/decisions/adr/0019-streamable-http.md", res)
        self.assertIn("docs/decisions/adr/0034-product-name-marrow.md", res)

    def test_parseFoundationalAdrPaths_noRolesColumn_returnsAllPaths(self):
        index_text = (
            "## Foundational ADRs 🔴\n"
            "| ID | Title | Status |\n"
            "|----|-------|--------|\n"
            "| 0007 | [Pipeline Standard](adr/0007-pipeline-standard.md) | Accepted |\n"
            "| 0019 | [Streamable HTTP Transport](adr/0019-streamable-http.md) | Accepted |\n"
        )
        from services.adr_service import _parse_foundational_adr_paths

        res = _parse_foundational_adr_paths(index_text, "execution")
        self.assertEqual(len(res), 2)
        self.assertIn("docs/decisions/adr/0007-pipeline-standard.md", res)
        self.assertIn("docs/decisions/adr/0019-streamable-http.md", res)

    def test_parseFoundationalAdrPaths_rowTaggedAll_alwaysIncluded(self):
        index_text = (
            "## Foundational ADRs 🔴\n"
            "| ID | Title | Status | Roles |\n"
            "|----|-------|--------|-------|\n"
            "| 0007 | [Pipeline Standard](adr/0007-pipeline-standard.md) | Accepted | all |\n"
        )
        from services.adr_service import _parse_foundational_adr_paths

        res = _parse_foundational_adr_paths(index_text, "ghost")
        self.assertEqual(res, ["docs/decisions/adr/0007-pipeline-standard.md"])


class TestGetGuidelineLogic(unittest.TestCase):
    _MOCK_YAML = """
roles:
  discovery:
    guideline: docs/manuals/guidelines/discovery.md
    adrs: ["0007", "0034"]
    playbooks: []
  execution:
    guideline: docs/manuals/guidelines/execution.md
    adrs: ["0007", "0019"]
    playbooks: []
"""

    _MOCK_INDEX = (
        "## Foundational ADRs 🔴\n"
        "| ID | Title | Status | Roles |\n"
        "|----|-------|--------|-------|\n"
        "| 0007 | [Pipeline Standard](adr/0007-pipeline-standard.md) | Accepted | all |\n"
        "| 0019 | [Streamable HTTP](adr/0019-streamable-http.md) | Accepted | execution |\n"
        "| 0034 | [Product Name](adr/0034-product-name-marrow.md) | Accepted | discovery |\n"
    )

    @patch("tools.artifacts.read_artifact_logic")
    def test_getGuidelineLogic_validRole_returnsFormattedBundle(self, mock_read):
        def side_effect(project, path):
            if path == "docs/manuals/guidelines/core.md":
                return "CORE"
            if path == "docs/manuals/role_profiles.yaml":
                return self._MOCK_YAML
            if path == "docs/manuals/guidelines/execution.md":
                return "EXECUTION GUIDELINE TEXT"
            if path == "docs/decisions/0000-index.md":
                return self._MOCK_INDEX
            if path == "docs/decisions/adr/0007-pipeline-standard.md":
                return "# Pipeline Standard\n## Summary\nPipeline summary."
            if path == "docs/decisions/adr/0019-streamable-http.md":
                return "# Streamable HTTP\n## Summary\nStreamable summary."
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        from tools.session_context import get_guideline_logic

        res = get_guideline_logic("TestProj", "execution")
        self.assertTrue(res.startswith("=== ROLE GUIDELINES ==="))
        self.assertIn("EXECUTION GUIDELINE TEXT", res)
        self.assertIn("=== FOUNDATIONAL DECISIONS ===", res)
        self.assertIn("Pipeline summary.", res)
        self.assertIn("Streamable summary.", res)

    @patch("tools.artifacts.read_artifact_logic")
    def test_getGuidelineLogic_unknownRole_returnsErrorString(self, mock_read):
        def side_effect(project, path):
            if path == "docs/manuals/guidelines/core.md":
                return "CORE"
            if path == "docs/manuals/role_profiles.yaml":
                return self._MOCK_YAML
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        from tools.session_context import get_guideline_logic

        res = get_guideline_logic("TestProj", "ghost")
        self.assertIn("Unknown role 'ghost'", res)

    @patch("tools.artifacts.read_artifact_logic")
    def test_getGuidelineLogic_missingYaml_returnsErrorString(self, mock_read):
        def side_effect(project, path):
            if path == "docs/manuals/guidelines/core.md":
                return "CORE"
            if path == "docs/manuals/role_profiles.yaml":
                raise ArtifactNotFoundError("file", "docs/manuals/role_profiles.yaml")
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        from tools.session_context import get_guideline_logic

        res = get_guideline_logic("TestProj", "execution")
        self.assertIn("role_profiles.yaml not found", res)

    @patch("tools.artifacts.read_artifact_logic")
    def test_getGuidelineLogic_missingGuidelineFile_returnsErrorString(self, mock_read):
        def side_effect(project, path):
            if path == "docs/manuals/guidelines/core.md":
                return "CORE"
            if path == "docs/manuals/role_profiles.yaml":
                return self._MOCK_YAML
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        from tools.session_context import get_guideline_logic

        res = get_guideline_logic("TestProj", "execution")
        self.assertIn("guideline file not found", res)

    @patch("tools.artifacts.read_artifact_logic")
    def test_getGuidelineLogic_missingAdrFile_skipsAndContinues(self, mock_read):
        def side_effect(project, path):
            if path == "docs/manuals/guidelines/core.md":
                return "CORE"
            if path == "docs/manuals/role_profiles.yaml":
                return self._MOCK_YAML
            if path == "docs/manuals/guidelines/execution.md":
                return "EXECUTION GUIDELINE TEXT"
            if path == "docs/decisions/0000-index.md":
                return self._MOCK_INDEX
            if path == "docs/decisions/adr/0007-pipeline-standard.md":
                return "# Pipeline Standard\n## Summary\nPipeline summary."
            raise ArtifactNotFoundError("file", path)

        mock_read.side_effect = side_effect
        from tools.session_context import get_guideline_logic

        with self.assertLogs("services.adr_service", level="WARNING") as log:
            res = get_guideline_logic("TestProj", "execution")
        self.assertIn("EXECUTION GUIDELINE TEXT", res)
        self.assertIn("Pipeline summary.", res)
        self.assertTrue(any("0019-streamable-http.md" in m for m in log.output))


class TestAgentProfileEngineFlag(unittest.TestCase):
    @patch("tools.artifacts.read_artifact_logic")
    def test_GetSessionContextLogic_FlagOn_ReturnsProfileOutput(self, mock_read):
        """Flag=True → guideline and ADRs resolved via RoleProfileLoader."""
        _MOCK_YAML = """
roles:
  architecture:
    guideline: docs/manuals/guidelines/architecture.md
    adrs: ["0007"]
    playbooks: []
"""
        _MOCK_INDEX = (
            "## Foundational ADRs 🔴\n"
            "| ID | Title | Status | Roles |\n"
            "|----|-------|--------|-------|\n"
            "| 0007 | [Pipeline Standard](adr/0007-pipeline-standard.md) | Accepted | all |\n"
        )

        def side_effect(project, path):
            if path == "session.md":
                return "Phase 4\nnext_agent_role: Architecture Agent"
            if path == "spec.md":
                return "SPEC"
            if path == "docs/manuals/guidelines/core.md":
                return "CORE"
            if path == "docs/manuals/role_profiles.yaml":
                return _MOCK_YAML
            if path == "docs/manuals/guidelines/architecture.md":
                return "ARCH GUIDELINE"
            if path == "docs/decisions/0000-index.md":
                return _MOCK_INDEX
            if path == "docs/decisions/adr/0007-pipeline-standard.md":
                return "# Pipeline Standard\n## Summary\nPipeline summary."
            raise ArtifactNotFoundError("x", path)

        mock_read.side_effect = side_effect

        import config

        with patch.object(config, "AGENT_PROFILE_ENGINE_ENABLED", True):
            result = get_session_context_logic("TestProj")

        self.assertIn("=== YOUR ROLE: Architecture Agent ===", result)
        self.assertIn("=== CORE GUIDELINES ===\nCORE", result)
        self.assertIn("=== PHASE GUIDELINES (Architecture Agent) ===\nARCH GUIDELINE", result)
        self.assertIn(
            "=== FOUNDATIONAL DECISIONS ===\n# Pipeline Standard\n**Source:** `docs/decisions/adr/0007-pipeline-standard.md`\n\nPipeline summary.",
            result,
        )

    def test_GetSessionContextLogic_DefaultFlag_IsTrue(self):
        """AGENT_PROFILE_ENGINE_ENABLED default value is True."""
        import importlib
        import os

        import config

        env_backup = os.environ.pop("AGENT_PROFILE_ENGINE_ENABLED", None)
        try:
            with patch("dotenv.load_dotenv"):
                importlib.reload(config)
                self.assertTrue(config.AGENT_PROFILE_ENGINE_ENABLED)
        finally:
            if env_backup is not None:
                os.environ["AGENT_PROFILE_ENGINE_ENABLED"] = env_backup
            with patch("dotenv.load_dotenv"):
                importlib.reload(config)


if __name__ == "__main__":
    unittest.main()
