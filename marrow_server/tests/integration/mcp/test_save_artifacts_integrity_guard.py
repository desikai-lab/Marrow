import os
import pytest

from config import PROJECTS_ROOT
from services.artifact_command_service import save_project_artifacts_logic

pytestmark = pytest.mark.integration


def _write_initial_file(tmp_project: str, rel_path: str, content: str):
    """Writes an initial state to a project file to prep it for hook/persister testing."""
    full_path = os.path.join(PROJECTS_ROOT, tmp_project, "artifacts", rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8-sig") as f:
        f.write(content)


def _read_project_file(tmp_project: str, rel_path: str) -> str:
    """Direct disk read, bypassing any MCP read path -- verifies what was
    actually persisted, not what a read tool reports."""
    full_path = os.path.join(PROJECTS_ROOT, tmp_project, "artifacts", rel_path)
    with open(full_path, encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def _read_history_head(tmp_project: str) -> str:
    """Returns current history.md content, or '' if it doesn't exist yet."""
    full_path = os.path.join(PROJECTS_ROOT, tmp_project, "artifacts", "docs/sessions/history.md")
    if not os.path.exists(full_path):
        return ""
    with open(full_path, encoding="utf-8-sig", errors="replace") as f:
        return f.read()


async def test_saveProjectArtifacts_replaceFileOnHistoryMd_rejectedWithValidationError(tmp_project):
    updates = [
        {
            "path": "docs/sessions/history.md",
            "mode": "replace_file",
            "content": "this should never be allowed",
        }
    ]
    results = await save_project_artifacts_logic(tmp_project, updates)
    assert results[0].status == "error"


async def test_saveProjectArtifacts_replaceFileOnSessionMd_repairsMissingHeader(tmp_project):
    _write_initial_file(tmp_project, "session.md", "# Session State\n**next_agent_role:** discovery\n")
    updates = [
        {
            "path": "session.md",
            "mode": "replace_file",
            "content": "**Current Task:** X\nno header here",
        }
    ]
    results = await save_project_artifacts_logic(tmp_project, updates)
    assert results[0].status == "success"
    persisted = _read_project_file(tmp_project, "session.md")
    assert "# Session State" in persisted
    assert "next_agent_role:" in persisted


async def test_saveProjectArtifacts_patchOnHistoryMd_succeedsAndPrepends(tmp_project):
    _write_initial_file(tmp_project, "docs/sessions/history.md", "# Session History\nInitial historical log.\n")
    current_head = _read_history_head(tmp_project)
    new_entry = "## Prepend-Test Entry A\n"
    updates = [
        {
            "path": "docs/sessions/history.md",
            "mode": "patch",
            "old_str": current_head,
            "content": new_entry + current_head,
        }
    ]
    results = await save_project_artifacts_logic(tmp_project, updates)
    assert results[0].status == "success"
    persisted = _read_project_file(tmp_project, "docs/sessions/history.md")
    assert persisted.startswith(new_entry)


async def test_saveProjectArtifacts_unguardedPath_unaffectedByHookLookup(tmp_project):
    updates = [
        {
            "path": "docs/features/active/unguarded-scratch-file.md",
            "mode": "replace_file",
            "content": "# Unguarded\n\nNo hook registered for this path.",
        }
    ]
    results = await save_project_artifacts_logic(tmp_project, updates)
    assert results[0].status == "success"
    persisted = _read_project_file(tmp_project, "docs/features/active/unguarded-scratch-file.md")
    assert "Unguarded" in persisted


async def test_saveProjectArtifacts_mixedModeBatchOnHistoryMd_secondPatchValidatesAgainstStaleDisk(tmp_project):
    _write_initial_file(tmp_project, "docs/sessions/history.md", "# Session History\nInitial historical log.\n")
    current_head = _read_history_head(tmp_project)
    entry_c = "## Batch-Test Entry C\n"
    entry_d = "## Batch-Test Entry D\n"
    updates = [
        {
            "path": "docs/sessions/history.md",
            "mode": "patch",
            "old_str": current_head,
            "content": entry_c + current_head,
        },
        {
            "path": "docs/sessions/history.md",
            "mode": "patch",
            "old_str": entry_c + current_head,
            "content": entry_d + entry_c + current_head,
        },
    ]
    results = await save_project_artifacts_logic(tmp_project, updates)
    assert results[0].status == "success"
    if results[1].status != "success":
        pytest.xfail(
        "Known limitation, out of scope for B4000198/B4000199 (see B4000192 "
        "implementation_plan.md Pre-Plan Audit): HistoryMdIntegrityHook re-reads "
        "the target file from disk on every call, so a second 'patch' update to the "
        "same guarded path within one batch validates against stale disk content, "
        f"not the first update's in-memory result. Observed: {results[1].status} - "
        f"{results[1].message}"
        )