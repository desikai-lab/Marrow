import shutil
from pathlib import Path

from migrator.runner import run_migrations_for_project
from tools import projects as projects_module


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_run_migrations_for_project_fresh_template_project_runs_no_migration(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    project = tmp_path / "Fresh"
    shutil.copytree(projects_module.TEMPLATE_DIR, project)
    before = _snapshot(project)

    report = run_migrations_for_project("Fresh")

    assert report.steps == []
    assert report.errors == []
    assert report.starting_version == report.ending_version == 3
    assert _snapshot(project) == before
