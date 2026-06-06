import pytest

from config import AGENT_PROFILE_ENGINE_ENABLED
from services.artifact_command_service import save_project_artifacts_logic
from tools.session_context import get_session_context_logic
from utils.exceptions import ArtifactNotFoundError

# Safety guard: this suite tests the legacy branch only
assert AGENT_PROFILE_ENGINE_ENABLED is False, (
    "APE-03 tests cover the legacy path. Set AGENT_PROFILE_ENGINE_ENABLED=False before running."
)

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
    await _write(proj, _SESSION, _SESSION_DISCOVERY)
    await _write(proj, _SPEC, _STUB)
    await _write(proj, _CORE, _STUB)
    await _write(proj, _DISCOVERY, _STUB)
    result = get_session_context_logic(proj)
    assert "=== YOUR ROLE: Discovery Agent ===" in result


async def test_get_session_context_logic_execution_phase_returns_execution_role_header(proj):
    await _write(proj, _SESSION, _SESSION_EXECUTION)
    await _write(proj, _SPEC, _STUB)
    await _write(proj, _CORE, _STUB)
    await _write(proj, _EXECUTION, _STUB)
    result = get_session_context_logic(proj)
    assert "=== YOUR ROLE: Execution Agent ===" in result


async def test_get_session_context_logic_next_agent_role_overrides_phase(proj):
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
    await _write(proj, _CORE, _STUB)
    await _write(proj, _DISCOVERY, _STUB)
    result = get_session_context_logic(proj)
    assert "=== YOUR ROLE: Discovery Agent ===" in result


async def test_get_session_context_logic_malformed_phase_defaults_to_discovery(proj):
    await _write(proj, _SESSION, _SESSION_BAD_PHASE)
    await _write(proj, _SPEC, _STUB)
    await _write(proj, _CORE, _STUB)
    await _write(proj, _DISCOVERY, _STUB)
    result = get_session_context_logic(proj)
    assert "=== YOUR ROLE: Discovery Agent ===" in result


async def test_get_session_context_logic_missing_adr_index_omits_decisions_section(proj):
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
    # discovery.md intentionally NOT written — GuidelinesFactory resolves to this path
    with pytest.raises(ArtifactNotFoundError):
        get_session_context_logic(proj)
