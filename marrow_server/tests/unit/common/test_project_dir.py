import pytest

from common.path_resolver import ResourceKind, get_dir_path
from common.project_file_error import ProjectFileError


def test_get_dir_path_valid_returns_project_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    project = "p1"
    docs_dir = tmp_path / project / "artifacts" / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "file.txt").write_text("hello", encoding="utf-8")

    pd = get_dir_path(project, "docs", ResourceKind.ARTIFACTS)
    assert pd.relative_path == "docs"
    assert pd.exists()
    assert pd.list_entries() == ["file.txt"]


def test_get_dir_path_traversal_raises_project_file_error():
    with pytest.raises(ProjectFileError):
        get_dir_path("p1", "../../etc", ResourceKind.ARTIFACTS)


def test_project_dir_child_resolution(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    project = "p1"
    docs_dir = tmp_path / project / "artifacts" / "docs"
    docs_dir.mkdir(parents=True)

    pd = get_dir_path(project, "docs", ResourceKind.ARTIFACTS)
    child_pp = pd.get_child_path("spec.md")
    assert child_pp.relative_path == "docs/spec.md"

    child_pd = pd.get_child_dir("sub")
    assert child_pd.relative_path == "docs/sub"

    with pytest.raises(ProjectFileError):
        pd.get_child_path("../secret.md")
