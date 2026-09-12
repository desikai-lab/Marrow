import os

import pytest

from migrator.migrations.local_storage_layout.v1_to_v2_history_folder_scheme import (
    V1ToV2HistoryFolderScheme,
)

NAMESPACE_ARTIFACTS = "artifacts"
NAMESPACE_TASKS = "tasks"


@pytest.fixture()
def project_root(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    root = tmp_path / "MyProject"
    root.mkdir(parents=True)
    return str(root)


def _history_namespace_dir(project_root: str, namespace: str) -> str:
    return os.path.join(project_root, ".history", namespace)


def _seed_old_scheme_file(project_root: str, namespace: str, rel_dir: str, name: str, ts: str, ext: str, content: str = "old content") -> str:
    target_dir = os.path.join(_history_namespace_dir(project_root, namespace), rel_dir)
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, f"{name}_{ts}{ext}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _new_scheme_path(project_root: str, namespace: str, rel_dir: str, name: str, ext: str, ts: str) -> str:
    return os.path.join(_history_namespace_dir(project_root, namespace), rel_dir, f"{name}{ext}", f"{ts}{ext}")


def test_apply_old_scheme_artifact_backups_moves_into_per_item_folders(project_root):
    src = _seed_old_scheme_file(project_root, NAMESPACE_ARTIFACTS, "docs", "spec", "20260501_120000", ".md")

    report = V1ToV2HistoryFolderScheme().apply(project_root)

    dest = _new_scheme_path(project_root, NAMESPACE_ARTIFACTS, "docs", "spec", ".md", "20260501_120000")
    assert os.path.exists(dest)
    assert not os.path.exists(src)
    assert report.moved == 1
    assert report.errors == []


def test_apply_old_scheme_task_backups_moves_into_per_item_folders(project_root):
    src = _seed_old_scheme_file(project_root, NAMESPACE_TASKS, "active", "TD4000200", "20260501_120000", ".md")

    report = V1ToV2HistoryFolderScheme().apply(project_root)

    dest = _new_scheme_path(project_root, NAMESPACE_TASKS, "active", "TD4000200", ".md", "20260501_120000")
    assert os.path.exists(dest)
    assert not os.path.exists(src)
    assert report.moved == 1


def test_apply_mixed_artifacts_and_tasks_namespaces_migrates_both(project_root):
    _seed_old_scheme_file(project_root, NAMESPACE_ARTIFACTS, "docs", "spec", "20260501_120000", ".md")
    _seed_old_scheme_file(project_root, NAMESPACE_TASKS, "active", "TD4000200", "20260501_130000", ".md")

    report = V1ToV2HistoryFolderScheme().apply(project_root)

    assert report.moved == 2
    assert os.path.exists(_new_scheme_path(project_root, NAMESPACE_ARTIFACTS, "docs", "spec", ".md", "20260501_120000"))
    assert os.path.exists(_new_scheme_path(project_root, NAMESPACE_TASKS, "active", "TD4000200", ".md", "20260501_130000"))


def test_apply_colliding_timestamp_backups_renames_without_overwriting(project_root):
    ts = "20260501_120000"
    src = _seed_old_scheme_file(project_root, NAMESPACE_ARTIFACTS, "docs", "spec", ts, ".md", content="old content")

    dest_dir = os.path.join(_history_namespace_dir(project_root, NAMESPACE_ARTIFACTS), "docs", "spec.md")
    os.makedirs(dest_dir, exist_ok=True)
    existing_dest = os.path.join(dest_dir, f"{ts}.md")
    with open(existing_dest, "w", encoding="utf-8") as f:
        f.write("new-scheme content")

    report = V1ToV2HistoryFolderScheme().apply(project_root)

    renamed = os.path.join(dest_dir, f"{ts}_migrated.md")
    assert os.path.exists(renamed)
    assert not os.path.exists(src)
    with open(renamed, encoding="utf-8") as f:
        assert f.read() == "old content"
    with open(existing_dest, encoding="utf-8") as f:
        assert f.read() == "new-scheme content"
    assert report.collisions == 1
    assert report.moved == 1


def test_apply_rerun_after_success_is_idempotent_no_op(project_root):
    _seed_old_scheme_file(project_root, NAMESPACE_ARTIFACTS, "docs", "spec", "20260501_120000", ".md")

    migration = V1ToV2HistoryFolderScheme()
    first = migration.apply(project_root)
    second = migration.apply(project_root)

    assert first.moved == 1
    assert second.moved == 0
    assert second.errors == []


def test_apply_no_history_directory_returns_empty_report_no_op(project_root):
    report = V1ToV2HistoryFolderScheme().apply(project_root)

    assert report.moved == 0
    assert report.collisions == 0
    assert report.errors == []


def test_apply_new_scheme_files_only_never_touched(project_root):
    dest_dir = os.path.join(_history_namespace_dir(project_root, NAMESPACE_ARTIFACTS), "docs", "spec.md")
    os.makedirs(dest_dir, exist_ok=True)
    new_scheme_file = os.path.join(dest_dir, "20260501_120000.md")
    with open(new_scheme_file, "w", encoding="utf-8") as f:
        f.write("already migrated")

    report = V1ToV2HistoryFolderScheme().apply(project_root)

    assert report.moved == 0
    with open(new_scheme_file, encoding="utf-8") as f:
        assert f.read() == "already migrated"


def test_apply_dry_run_reports_planned_moves_without_touching_filesystem(project_root):
    src = _seed_old_scheme_file(project_root, NAMESPACE_ARTIFACTS, "docs", "spec", "20260501_120000", ".md")

    report = V1ToV2HistoryFolderScheme().apply(project_root, dry_run=True)

    dest_dir = os.path.join(_history_namespace_dir(project_root, NAMESPACE_ARTIFACTS), "docs", "spec.md")
    assert report.moved == 1
    assert os.path.exists(src)
    assert not os.path.exists(dest_dir)


def test_apply_unreadable_file_counts_error_without_aborting_other_files(project_root, monkeypatch):
    src_a = _seed_old_scheme_file(project_root, NAMESPACE_ARTIFACTS, "docs", "spec", "20260501_120000", ".md")
    _seed_old_scheme_file(project_root, NAMESPACE_ARTIFACTS, "docs", "readme", "20260502_090000", ".md")

    real_rename = os.rename

    def flaky_rename(src, dst):
        if src == src_a:
            raise OSError("simulated unreadable/locked file")
        return real_rename(src, dst)

    def flaky_copy2(*args, **kwargs):
        raise OSError("simulated copy failure")

    monkeypatch.setattr("os.rename", flaky_rename)
    monkeypatch.setattr("shutil.copy2", flaky_copy2)

    report = V1ToV2HistoryFolderScheme().apply(project_root)

    assert report.moved == 1
    assert len(report.errors) == 1
    assert report.errors[0]["file"] == src_a
