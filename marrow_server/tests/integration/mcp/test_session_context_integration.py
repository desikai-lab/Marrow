import pytest

from config import AGENT_PROFILE_ENGINE_ENABLED
from services.artifact_command_service import save_project_artifacts_logic
from tools.session_context import get_session_context_logic
from utils.exceptions import ArtifactNotFoundError

# APE-04: guard removed — output format is identical on both flag-on and flag-off paths.

pytestmark = pytest.mark.integration


@pytest.fixture()
def proj(tmp_project, tmp_path):
    """Function-scoped isolated project. Each test gets a clean namespace."""
    import os

    from config import PROJECTS_ROOT
    from storage.db import init_db

    project_name = f"test_sc_{tmp_path.name}"
    project_dir = os.path.join(PROJECTS_ROOT, project_name)
    os.makedirs(project_dir, exist_ok=True)
    init_db(project_dir)
    return project_name


async def _write(project: str, path: str, content: str) -> None:
    """Thin helper: write a single artifact into `project`."""
    await save_project_artifacts_logic(
        project,
        [{"path": path, "mode": "replace_file", "content": content}],
    )


# Minimal role_profiles.yaml stub — only needed by the flag-on path.
_ROLE_PROFILES_CONTENT = """\
roles:
  discovery:
    guideline: docs/manuals/guidelines/discovery.md
    adrs: []
    playbooks: []
  architecture:
    guideline: docs/manuals/guidelines/architecture.md
    adrs: []
    playbooks: []
  planning:
    guideline: docs/manuals/guidelines/planning.md
    adrs: []
    playbooks: []
  execution:
    guideline: docs/manuals/guidelines/execution.md
    adrs: []
    playbooks: []
"""


async def _write_profiles_if_ape(project: str) -> None:
    """Write role_profiles.yaml when the APE flag is on; no-op otherwise."""
    if AGENT_PROFILE_ENGINE_ENABLED:
        await _write(project, "docs/manuals/role_profiles.yaml", _ROLE_PROFILES_CONTENT)


_STUB = "# stub\nminimal content for testing\n"
_SESSION_DISCOVERY = "# Session\nPhase: 2\n"
_SESSION_EXECUTION = "# Session\nPhase: 12\n"
_SESSION_OVERRIDE = "# Session\nPhase: 2\nnext_agent_role: Execution Agent\n"
_SESSION_BAD_PHASE = "# Session\nPhase: not-a-number\n"

_CORE = "docs/manuals/guidelines/core.md"
_DISCOVERY = "docs/manuals/guidelines/discovery.md"
_EXECUTION = "docs/manuals/guidelines/execution.md"
_SESSION = "session.md"
_SPEC = "spec.md"
_ADR_INDEX = "docs/decisions/0000-index.md"


async def test_get_session_context_logic_discovery_phase_returns_discovery_role_header(proj):
    await _write_profiles_if_ape(proj)
    await _write(proj, _SESSION, _SESSION_DISCOVERY)
    await _write(proj, _SPEC, _STUB)
    await _write(proj, _CORE, _STUB)
    await _write(proj, _DISCOVERY, _STUB)
    result = get_session_context_logic(proj)
    assert "=== YOUR ROLE: Discovery Agent ===" in result


async def test_get_session_context_logic_execution_phase_returns_execution_role_header(proj):
    await _write_profiles_if_ape(proj)
    await _write(proj, _SESSION, _SESSION_EXECUTION)
    await _write(proj, _SPEC, _STUB)
    await _write(proj, _CORE, _STUB)
    await _write(proj, _EXECUTION, _STUB)
    result = get_session_context_logic(proj)
    assert "=== YOUR ROLE: Execution Agent ===" in result


async def test_get_session_context_logic_next_agent_role_overrides_phase(proj):
    await _write_profiles_if_ape(proj)
    await _write(proj, _SESSION, _SESSION_OVERRIDE)
    await _write(proj, _SPEC, _STUB)
    await _write(proj, _CORE, _STUB)
    await _write(proj, _EXECUTION, _STUB)
    result = get_session_context_logic(proj)
    assert "Execution Agent" in result
    # Role header must NOT resolve to Discovery despite Phase: 2
    assert "=== YOUR ROLE: Discovery Agent ===" not in result


async def test_get_session_context_logic_missing_session_file_defaults_to_discovery(proj):
    # session.md intentionally NOT written
    await _write_profiles_if_ape(proj)
    await _write(proj, _CORE, _STUB)
    await _write(proj, _DISCOVERY, _STUB)
    result = get_session_context_logic(proj)
    assert "=== YOUR ROLE: Discovery Agent ===" in result


async def test_get_session_context_logic_malformed_phase_defaults_to_discovery(proj):
    await _write_profiles_if_ape(proj)
    await _write(proj, _SESSION, _SESSION_BAD_PHASE)
    await _write(proj, _SPEC, _STUB)
    await _write(proj, _CORE, _STUB)
    await _write(proj, _DISCOVERY, _STUB)
    result = get_session_context_logic(proj)
    assert "=== YOUR ROLE: Discovery Agent ===" in result


async def test_get_session_context_logic_missing_adr_index_omits_decisions_section(proj):
    await _write_profiles_if_ape(proj)
    await _write(proj, _SESSION, _SESSION_DISCOVERY)
    await _write(proj, _SPEC, _STUB)
    await _write(proj, _CORE, _STUB)
    await _write(proj, _DISCOVERY, _STUB)
    # ADR index intentionally NOT written
    result = get_session_context_logic(proj)
    # No ADR heading should appear in output
    assert "# ADR" not in result
    assert "# 0" not in result  # ADR entries start with "# 00NN"


async def test_get_session_context_logic_missing_guideline_file_raises_artifact_not_found(proj):
    await _write(proj, _SESSION, _SESSION_DISCOVERY)
    await _write(proj, _SPEC, _STUB)
    await _write(proj, _CORE, _STUB)
    # discovery.md intentionally NOT written
    if AGENT_PROFILE_ENGINE_ENABLED:
        # Flag-on: RoleProfileLoader catches missing file, returns error string (REQ-05)
        await _write_profiles_if_ape(proj)
        result = get_session_context_logic(proj)
        assert "Error: guideline file not found" in result
    else:
        # Flag-off: GuidelinesFactory path propagates ArtifactNotFoundError (legacy contract)
        with pytest.raises(ArtifactNotFoundError):
            get_session_context_logic(proj)
