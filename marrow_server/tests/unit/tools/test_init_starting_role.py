from pathlib import Path
from unittest.mock import patch

import pytest

import config
from services.session_service import _parse_next_agent
from tools import projects as projects_module

FLAGS = ("CODE_ENABLED", "TASK_ENABLED", "BUILD_ENABLED")
SESSION = "artifacts/session.md"
FORBIDDEN_IN_SESSION = (
    "search_code_skeletons",
    "get_file_skeleton",
    "get_project_map",
    "view_file_source",
    "add_tasks",
    "search_tasks",
    "get_task_details",
    "update_task",
    "complete_tasks",
    "run_project_build",
    "TOOL_GROUP",
)


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _init(tmp_path: Path, name: str):
    projects = tmp_path / name
    # init_project_logic creates the directory from tools.projects.PROJECTS_ROOT, while the path
    # resolver reads config.PROJECTS_ROOT: in production both are the same value, so patch both.
    with (
        patch("tools.projects.PROJECTS_ROOT", str(projects)),
        patch("config.PROJECTS_ROOT", str(projects)),
    ):
        result = projects_module.init_project_logic("Proj")
    return result, _snapshot(projects / "Proj")


def _set_flags(monkeypatch, **values):
    for flag in FLAGS:
        monkeypatch.setattr(config, flag, values.get(flag, True))


def test_init_project_logic_all_groups_enabled_tree_equals_template(tmp_path, monkeypatch):
    _set_flags(monkeypatch)

    result, tree = _init(tmp_path, "on")

    assert result.starting_role == "Discovery Agent"
    assert tree == _snapshot(Path(projects_module.TEMPLATE_DIR))


@pytest.mark.parametrize(
    "off", [("CODE_ENABLED",), ("TASK_ENABLED",), ("CODE_ENABLED", "TASK_ENABLED")]
)
def test_init_project_logic_group_disabled_changes_only_session_md(tmp_path, monkeypatch, off):
    _set_flags(monkeypatch)
    base_result, base_tree = _init(tmp_path, "base")
    _set_flags(monkeypatch, **{flag: False for flag in off})

    result, tree = _init(tmp_path, "off")

    assert result.starting_role == "Init Agent"
    assert sorted(result.files_created) == sorted(base_result.files_created)
    assert {path for path in tree if tree[path] != base_tree[path]} == {SESSION}
    session = tree[SESSION].decode("utf-8-sig")  # the engine writes artifacts with a BOM
    assert session.startswith("# Session State")
    assert _parse_next_agent(session) == "Init Agent"
    for name in FORBIDDEN_IN_SESSION:
        assert name not in session, name


def test_init_project_logic_build_group_disabled_keeps_default_start(tmp_path, monkeypatch):
    _set_flags(monkeypatch, BUILD_ENABLED=False)

    result, tree = _init(tmp_path, "build_off")

    assert result.starting_role == "Discovery Agent"
    assert tree == _snapshot(Path(projects_module.TEMPLATE_DIR))


def test_init_project_logic_group_disabled_with_bare_template_still_succeeds(tmp_path, monkeypatch):
    _set_flags(monkeypatch, CODE_ENABLED=False)
    template = tmp_path / "tpl"
    template.mkdir()
    (template / "spec.md").write_bytes(b"spec")
    projects = tmp_path / "projects"

    with (
        patch("tools.projects.PROJECTS_ROOT", str(projects)),
        patch("config.PROJECTS_ROOT", str(projects)),
        patch("tools.projects.TEMPLATE_DIR", str(template)),
    ):
        result = projects_module.init_project_logic("Proj")

    assert result.starting_role == "Init Agent"
    assert (projects / "Proj" / "artifacts" / "session.md").is_file()
