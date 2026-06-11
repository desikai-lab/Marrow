import os
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.session_context import get_guideline_logic, get_session_context_logic

PROJECT = "TestProject"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestGetGuidelineLogicIntegration(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmp = tempfile.mkdtemp()
        self.artifacts = Path(self.tmp) / PROJECT / "artifacts"
        self._build_fixture()
        self.patchers = [
            patch("config.PROJECTS_ROOT", self.tmp),
            patch("tools.utils.filesystem_utils.PROJECTS_ROOT", self.tmp),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build_fixture(self):
        a = self.artifacts
        _write(
            a / "docs/manuals/role_profiles.yaml",
            """
roles:
  discovery:
    guideline: docs/manuals/guidelines/discovery.md
    adrs: ["0007", "0034"]
    playbooks: []
  execution:
    guideline: docs/manuals/guidelines/execution.md
    adrs: ["0007"]
    playbooks: []
""",
        )
        _write(
            a / "docs/manuals/guidelines/discovery.md",
            "# Discovery Agent Guidelines\nDiscover things.",
        )
        _write(
            a / "docs/manuals/guidelines/execution.md",
            "# Execution Agent Guidelines\nExecute things.",
        )
        _write(a / "docs/manuals/guidelines/core.md", "# Core Guidelines\nCore rules.")
        _write(a / "docs/manuals/guidelines/planning.md", "# Planning Guidelines\nPlaceholder.")
        _write(
            a / "docs/manuals/guidelines/architecture.md", "# Architecture Guidelines\nPlaceholder."
        )
        _write(
            a / "docs/decisions/0000-index.md",
            """
## Foundational ADRs

| ID | Title | Status | Roles |
|----|-------|--------|-------|
| [0007](adr/0007-pipeline-standard.md) | Pipeline Standard | Accepted | all |
| [0034](adr/0034-product-name-marrow.md) | Product Name | Accepted | discovery |
""",
        )
        _write(
            a / "docs/decisions/adr/0007-pipeline-standard.md",
            "# ADR-07: Pipeline Standard\n\n## Summary\nEvery task follows a mandatory pipeline.",
        )
        _write(
            a / "docs/decisions/adr/0034-product-name-marrow.md",
            "# ADR-0034: Product Name\n\n## Summary\nThe public product name is Marrow.",
        )
        _write(a / "session.md", "**Phase:** 12\nnext_agent_role: Execution Agent")
        _write(a / "spec.md", "# Spec\nTest spec.")

    def test_getGuidelineLogic_discoveryRole_returnsGuidelineAndCorrectAdrs(self):
        result = get_guideline_logic(PROJECT, "discovery")
        self.assertIn("=== ROLE GUIDELINES ===", result)
        self.assertIn("Discover things.", result)
        self.assertIn("=== FOUNDATIONAL DECISIONS ===", result)
        # ADR-0034 tagged discovery — must be present
        self.assertIn("Product Name", result)
        # ADR-0007 tagged all — must also be present
        self.assertIn("Pipeline Standard", result)

    def test_getGuidelineLogic_executionRole_returnsGuidelineAndCorrectAdrs(self):
        result = get_guideline_logic(PROJECT, "execution")
        self.assertIn("Execute things.", result)
        # Only ADR-0007 in execution profile
        self.assertIn("Pipeline Standard", result)
        # ADR-0034 NOT in execution profile — must be absent
        self.assertNotIn("Product Name", result)

    def test_getGuidelineLogic_unknownRole_returnsErrorString(self):
        result = get_guideline_logic(PROJECT, "ghost")
        self.assertIsInstance(result, str)
        self.assertIn("Unknown role", result)
        self.assertIn("discovery", result)
        self.assertIn("execution", result)

    def test_getGuidelineLogic_missingYaml_returnsErrorString(self):
        os.remove(self.artifacts / "docs/manuals/role_profiles.yaml")
        result = get_guideline_logic(PROJECT, "discovery")
        self.assertIn("role_profiles.yaml not found", result)


class TestGetSessionContextRoleFilteringIntegration(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmp = tempfile.mkdtemp()
        self.artifacts = Path(self.tmp) / PROJECT / "artifacts"
        self._build_fixture()
        self.patchers = [
            patch("config.PROJECTS_ROOT", self.tmp),
            patch("tools.utils.filesystem_utils.PROJECTS_ROOT", self.tmp),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build_fixture(self):
        a = self.artifacts
        _write(
            a / "docs/manuals/role_profiles.yaml",
            """
roles:
  discovery:
    guideline: docs/manuals/guidelines/discovery.md
    adrs: ["0007", "0034"]
    playbooks: []
  execution:
    guideline: docs/manuals/guidelines/execution.md
    adrs: ["0007"]
    playbooks: []
""",
        )
        _write(a / "docs/manuals/guidelines/core.md", "# Core Guidelines\nCore rules.")
        _write(a / "docs/manuals/guidelines/discovery.md", "# Discovery Guidelines\nDiscover.")
        _write(a / "docs/manuals/guidelines/execution.md", "# Execution Guidelines\nExecute.")
        _write(a / "docs/manuals/guidelines/planning.md", "# Planning Guidelines\nPlan.")
        _write(
            a / "docs/manuals/guidelines/architecture.md", "# Architecture Guidelines\nArchitect."
        )
        _write(
            a / "docs/decisions/0000-index.md",
            """
## Foundational ADRs

| ID | Title | Status | Roles |
|----|-------|--------|-------|
| [0007](adr/0007-pipeline-standard.md) | Pipeline Standard | Accepted | all |
| [0034](adr/0034-product-name-marrow.md) | Product Name | Accepted | discovery |
""",
        )
        _write(
            a / "docs/decisions/adr/0007-pipeline-standard.md",
            "# ADR-07: Pipeline Standard\n\n## Summary\nEvery task follows a mandatory pipeline.",
        )
        _write(
            a / "docs/decisions/adr/0034-product-name-marrow.md",
            "# ADR-0034: Product Name\n\n## Summary\nThe public product name is Marrow.",
        )
        _write(a / "spec.md", "# Spec\nTest spec.")

    def test_getSessionContext_executionAgent_excludesDiscoveryOnlyAdr(self):
        _write(self.artifacts / "session.md", "**Phase:** 12\nnext_agent_role: Execution Agent")
        result = get_session_context_logic(PROJECT)
        self.assertIn("Pipeline Standard", result)  # tagged all — must be present
        self.assertNotIn("Product Name", result)  # tagged discovery — must be absent

    def test_getSessionContext_discoveryAgent_includesDiscoveryAdr(self):
        _write(self.artifacts / "session.md", "**Phase:** 1\nnext_agent_role: Discovery Agent")
        result = get_session_context_logic(PROJECT)
        self.assertIn("Pipeline Standard", result)  # all
        self.assertIn("Product Name", result)  # discovery

    def test_getSessionContext_executionAgent_roleHeaderPresent(self):
        _write(self.artifacts / "session.md", "**Phase:** 12\nnext_agent_role: Execution Agent")
        result = get_session_context_logic(PROJECT)
        self.assertIn("=== YOUR ROLE: Execution Agent ===", result)


class TestGetSessionContextFlagParity(unittest.TestCase):
    """APE-05: Assert full output parity between flag-off and flag-on paths
    for all four agent roles. These tests are the validation gate before
    GuidelinesFactory dead-code removal."""

    import shutil
    import tempfile

    ROLES = [
        ("Discovery Agent", "**Phase:** 1\nnext_agent_role: Discovery Agent"),
        ("Architecture Agent", "**Phase:** 4\nnext_agent_role: Architecture Agent"),
        ("Planning Agent", "**Phase:** 7\nnext_agent_role: Planning Agent"),
        ("Execution Agent", "**Phase:** 12\nnext_agent_role: Execution Agent"),
    ]

    def setUp(self):
        import tempfile

        self.tmp = tempfile.mkdtemp()
        self.artifacts = Path(self.tmp) / PROJECT / "artifacts"
        self._build_fixture()
        self.patchers = [
            patch("config.PROJECTS_ROOT", self.tmp),
            patch("tools.utils.filesystem_utils.PROJECTS_ROOT", self.tmp),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build_fixture(self):
        a = self.artifacts
        _write(
            a / "docs/manuals/role_profiles.yaml",
            """
roles:
  discovery:
    guideline: docs/manuals/guidelines/discovery.md
    adrs: ["0007", "0034"]
    playbooks: []
  architecture:
    guideline: docs/manuals/guidelines/architecture.md
    adrs: ["0007"]
    playbooks: []
  planning:
    guideline: docs/manuals/guidelines/planning.md
    adrs: ["0007"]
    playbooks: []
  execution:
    guideline: docs/manuals/guidelines/execution.md
    adrs: ["0007"]
    playbooks: []
""",
        )
        _write(a / "docs/manuals/guidelines/core.md", "# Core Guidelines\nCore rules.")
        _write(a / "docs/manuals/guidelines/discovery.md", "# Discovery Guidelines\nDiscover.")
        _write(
            a / "docs/manuals/guidelines/architecture.md", "# Architecture Guidelines\nArchitect."
        )
        _write(a / "docs/manuals/guidelines/planning.md", "# Planning Guidelines\nPlan.")
        _write(a / "docs/manuals/guidelines/execution.md", "# Execution Guidelines\nExecute.")
        _write(
            a / "docs/decisions/0000-index.md",
            """
## Foundational ADRs

| ID | Title | Status | Roles |
|----|-------|--------|-------|
| [0007](adr/0007-pipeline-standard.md) | Pipeline Standard | Accepted | all |
| [0034](adr/0034-product-name-marrow.md) | Product Name | Accepted | discovery |
""",
        )
        _write(
            a / "docs/decisions/adr/0007-pipeline-standard.md",
            "# ADR-07: Pipeline Standard\n\n## Summary\nEvery task follows a mandatory pipeline.",
        )
        _write(
            a / "docs/decisions/adr/0034-product-name-marrow.md",
            "# ADR-0034: Product Name\n\n## Summary\nThe public product name is Marrow.",
        )
        _write(a / "spec.md", "# Spec\nTest spec.")

    def _run_with_flag(self, session_content: str, flag: bool) -> str:
        _write(self.artifacts / "session.md", session_content)
        with patch("config.AGENT_PROFILE_ENGINE_ENABLED", flag):
            return get_session_context_logic(PROJECT)

    def test_flagParity_discoveryAgent_outputIdentical(self):
        role, session = self.ROLES[0]
        off = self._run_with_flag(session, False)
        on = self._run_with_flag(session, True)
        self.assertEqual(off, on, f"Flag-off/on output diverged for {role}")

    def test_flagParity_architectureAgent_outputIdentical(self):
        role, session = self.ROLES[1]
        off = self._run_with_flag(session, False)
        on = self._run_with_flag(session, True)
        self.assertEqual(off, on, f"Flag-off/on output diverged for {role}")

    def test_flagParity_planningAgent_outputIdentical(self):
        role, session = self.ROLES[2]
        off = self._run_with_flag(session, False)
        on = self._run_with_flag(session, True)
        self.assertEqual(off, on, f"Flag-off/on output diverged for {role}")

    def test_flagParity_executionAgent_outputIdentical(self):
        role, session = self.ROLES[3]
        off = self._run_with_flag(session, False)
        on = self._run_with_flag(session, True)
        self.assertEqual(off, on, f"Flag-off/on output diverged for {role}")
