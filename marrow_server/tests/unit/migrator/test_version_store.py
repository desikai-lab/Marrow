import pytest
import yaml

from migrator.version_store import (
    ProjectMeta,
    get_subsystem_version,
    load_project_meta,
    save_project_meta,
)


@pytest.fixture()
def tmp_project(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    project_dir = tmp_path / "MyProject"
    project_dir.mkdir(parents=True)
    return project_dir


def test_load_project_meta_no_file_exists_returns_default_empty_versions(tmp_project):
    meta = load_project_meta("MyProject")
    assert meta.schema_versions == {}
    assert get_subsystem_version(meta, "local_storage_layout") == 1


def test_load_project_meta_existing_file_parses_schema_versions_and_plugins(tmp_project):
    marrow_dir = tmp_project / ".marrow"
    marrow_dir.mkdir(parents=True)
    payload = {
        "schema_versions": {"local_storage_layout": 2},
        "plugins": {"example_plugin": {"enabled": True}},
    }
    with open(marrow_dir / "project.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f)

    meta = load_project_meta("MyProject")

    assert meta.schema_versions == {"local_storage_layout": 2}
    assert meta.plugins == {"example_plugin": {"enabled": True}}


def test_save_project_meta_then_load_round_trips_correctly(tmp_project):
    meta = ProjectMeta(
        schema_versions={"local_storage_layout": 2},
        plugins={"example_plugin": {"enabled": True}},
    )

    save_project_meta("MyProject", meta)
    reloaded = load_project_meta("MyProject")

    assert reloaded.schema_versions == meta.schema_versions
    assert reloaded.plugins == meta.plugins


def test_save_project_meta_writes_atomically_no_temp_file_left_behind(tmp_project):
    meta = ProjectMeta(schema_versions={"local_storage_layout": 2})

    save_project_meta("MyProject", meta)

    marrow_dir = tmp_project / ".marrow"
    assert not (marrow_dir / "project.yaml.tmp").exists()
    assert (marrow_dir / "project.yaml").exists()


def test_save_project_meta_creates_marrow_dir_if_absent(tmp_project):
    marrow_dir = tmp_project / ".marrow"
    assert not marrow_dir.exists()

    meta = ProjectMeta(schema_versions={"local_storage_layout": 1})
    save_project_meta("MyProject", meta)

    assert marrow_dir.exists()
    assert (marrow_dir / "project.yaml").exists()
