from unittest.mock import MagicMock

import pytest

import migrator.runner as runner_module
from migrator.base import Migration, MigrationStepReport
from migrator.runner import run_migrations_all_projects, run_migrations_for_project
from migrator.version_store import load_project_meta


class DummyStep1(Migration):
    subsystem = "local_storage_layout"
    from_version = 1
    to_version = 2

    def apply(self, project_root: str, dry_run: bool = False) -> MigrationStepReport:
        return MigrationStepReport(subsystem=self.subsystem, from_version=1, to_version=2, moved=5)


class DummyStep2(Migration):
    subsystem = "local_storage_layout"
    from_version = 2
    to_version = 3

    def apply(self, project_root: str, dry_run: bool = False) -> MigrationStepReport:
        return MigrationStepReport(subsystem=self.subsystem, from_version=2, to_version=3, moved=3)


class RaisingStep2(Migration):
    subsystem = "local_storage_layout"
    from_version = 2
    to_version = 3

    def apply(self, project_root: str, dry_run: bool = False) -> MigrationStepReport:
        raise RuntimeError("simulated step 2 failure")


@pytest.fixture()
def projects_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    p1 = tmp_path / "Proj1"
    p1.mkdir(parents=True)
    return tmp_path


def test_run_migrations_for_project_fresh_project_applies_all_pending_steps_in_order(projects_dir, monkeypatch):
    monkeypatch.setattr(runner_module, "LOCAL_STORAGE_LAYOUT_REGISTRY", [DummyStep1(), DummyStep2()])

    report = run_migrations_for_project("Proj1")

    assert report.starting_version == 1
    assert report.ending_version == 3
    assert len(report.steps) == 2
    assert report.steps[0].to_version == 2
    assert report.steps[1].to_version == 3
    assert report.errors == []

    meta = load_project_meta("Proj1")
    assert meta.schema_versions["local_storage_layout"] == 3


def test_run_migrations_for_project_already_at_head_version_no_op_skips_apply(projects_dir, monkeypatch):
    mock_step1 = MagicMock(spec=Migration)
    mock_step1.subsystem = "local_storage_layout"
    mock_step1.from_version = 1
    mock_step1.to_version = 2

    mock_step2 = MagicMock(spec=Migration)
    mock_step2.subsystem = "local_storage_layout"
    mock_step2.from_version = 2
    mock_step2.to_version = 3

    monkeypatch.setattr(runner_module, "LOCAL_STORAGE_LAYOUT_REGISTRY", [mock_step1, mock_step2])

    from migrator.version_store import ProjectMeta, save_project_meta

    save_project_meta("Proj1", ProjectMeta(schema_versions={"local_storage_layout": 3}))

    report = run_migrations_for_project("Proj1")

    assert report.starting_version == 3
    assert report.ending_version == 3
    assert report.steps == []
    mock_step1.apply.assert_not_called()
    mock_step2.apply.assert_not_called()


def test_run_migrations_for_project_step_raises_stops_without_bumping_version_past_failure(projects_dir, monkeypatch):
    monkeypatch.setattr(runner_module, "LOCAL_STORAGE_LAYOUT_REGISTRY", [DummyStep1(), RaisingStep2()])

    report = run_migrations_for_project("Proj1")

    assert report.starting_version == 1
    assert report.ending_version == 2
    assert len(report.steps) == 1
    assert len(report.errors) == 1
    assert "simulated step 2 failure" in report.errors[0]["error"]

    meta = load_project_meta("Proj1")
    assert meta.schema_versions["local_storage_layout"] == 2


def test_run_migrations_for_project_crash_simulated_between_steps_resumes_from_last_persisted_version_on_rerun(projects_dir, monkeypatch):
    monkeypatch.setattr(runner_module, "LOCAL_STORAGE_LAYOUT_REGISTRY", [DummyStep1(), RaisingStep2()])
    first_report = run_migrations_for_project("Proj1")
    assert first_report.ending_version == 2

    monkeypatch.setattr(runner_module, "LOCAL_STORAGE_LAYOUT_REGISTRY", [DummyStep1(), DummyStep2()])
    second_report = run_migrations_for_project("Proj1")

    assert second_report.starting_version == 2
    assert second_report.ending_version == 3
    assert len(second_report.steps) == 1
    assert second_report.steps[0].from_version == 2
    assert second_report.steps[0].to_version == 3


def test_run_migrations_for_project_dry_run_does_not_persist_version_bump(projects_dir, monkeypatch):
    monkeypatch.setattr(runner_module, "LOCAL_STORAGE_LAYOUT_REGISTRY", [DummyStep1(), DummyStep2()])

    report = run_migrations_for_project("Proj1", dry_run=True)

    assert report.starting_version == 1
    assert report.ending_version == 3
    assert len(report.steps) == 2

    meta = load_project_meta("Proj1")
    assert meta.schema_versions.get("local_storage_layout") is None


def test_run_migrations_all_projects_multiple_projects_one_fails_isolates_failure_continues_others(projects_dir, monkeypatch):
    p2 = projects_dir / "Proj2"
    p2.mkdir(parents=True)

    def fake_run_for_project(project_name, dry_run=False):
        if project_name == "Proj1":
            raise RuntimeError("simulated project failure")
        return runner_module.MigrationReport(project=project_name, subsystem="local_storage_layout", starting_version=1, ending_version=2)

    monkeypatch.setattr(runner_module, "run_migrations_for_project", fake_run_for_project)

    reports = run_migrations_all_projects()

    assert len(reports) == 2
    proj1_rep = next(r for r in reports if r.project == "Proj1")
    proj2_rep = next(r for r in reports if r.project == "Proj2")

    assert len(proj1_rep.errors) == 1
    assert proj2_rep.ending_version == 2


def test_run_migrations_all_projects_no_projects_root_dir_returns_empty_list(monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", "D:/nonexistent_path_xyz_123")

    reports = run_migrations_all_projects()
    assert reports == []
