import os
import shutil

import pytest

import config
from migrator.runner import run_migrations_for_project
from services.role_profile_service import RoleProfile, RoleProfileLoader
from storage.db import init_db
from tools.projects import init_project_logic
from tools.session_context import get_session_context_logic

pytestmark = pytest.mark.integration


@pytest.fixture()
def project(tmp_path, monkeypatch):
    name = f"init_flow_{tmp_path.name}"
    monkeypatch.setattr("tools.projects.PROJECTS_ROOT", config.PROJECTS_ROOT)
    for flag in ("CODE_ENABLED", "TASK_ENABLED", "BUILD_ENABLED"):
        monkeypatch.setattr(config, flag, True)
    yield name
    shutil.rmtree(os.path.join(config.PROJECTS_ROOT, name), ignore_errors=True)


def _root(name):
    return os.path.join(config.PROJECTS_ROOT, name)


def _session_bytes(name):
    with open(os.path.join(_root(name), "artifacts", "session.md"), "rb") as handle:
        return handle.read()


def test_init_then_get_session_context_task_group_disabled_returns_init_role_and_hard_stop(
    project, monkeypatch
):
    monkeypatch.setattr(config, "TASK_ENABLED", False)
    result = init_project_logic(project)
    init_db(_root(project))

    context = get_session_context_logic(project)

    assert result.starting_role == "Init Agent"
    assert "=== YOUR ROLE: Init Agent ===" in context
    assert "Protocol B" in context
    assert "HARD STOP" in context
    assert "Next role on approval: discovery" in context


def test_get_session_context_start_role_init_does_not_change_session_md(project):
    init_project_logic(project)
    init_db(_root(project))
    before = _session_bytes(project)

    context = get_session_context_logic(project, start_role="init")

    assert "=== YOUR ROLE: init ===" in context
    assert "Protocol A" in context
    assert "=== SESSION STATE ===" not in context
    assert _session_bytes(project) == before


def _downgrade_to_pre_init_agent(root):
    profiles = os.path.join(root, "artifacts", "docs", "manuals", "role_profiles.yaml")
    with open(profiles, encoding="utf-8", newline="") as handle:
        text = handle.read()
    head, marker, _ = text.partition("  init:")
    assert marker, "the template must ship the init role"
    with open(profiles, "w", encoding="utf-8", newline="") as handle:
        handle.write(head)
    guideline = os.path.join(root, "artifacts", "docs", "manuals", "guidelines", "init.md")
    os.remove(guideline)
    meta = os.path.join(root, ".marrow", "project.yaml")
    with open(meta, "w", encoding="utf-8", newline="") as handle:
        handle.write("schema_versions:\n  local_storage_layout: 2\nplugins: {}\n")


def test_migration_on_project_created_before_init_agent_adds_role_and_resolves(project):
    init_project_logic(project)
    root = _root(project)
    init_db(root)
    _downgrade_to_pre_init_agent(root)
    session_before = _session_bytes(project)

    report = run_migrations_for_project(project)

    assert (report.starting_version, report.ending_version) == (2, 3)
    assert report.errors == []
    assert report.steps[0].moved == 2
    context = get_session_context_logic(project, start_role="init")
    assert "Protocol A" in context
    profiles = os.path.join(root, "artifacts", "docs", "manuals", "role_profiles.yaml")
    with open(profiles, encoding="utf-8") as handle:
        assert isinstance(RoleProfileLoader().get_profile(handle.read(), "init"), RoleProfile)
    assert _session_bytes(project) == session_before
