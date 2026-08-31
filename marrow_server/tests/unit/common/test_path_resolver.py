import os
from unittest.mock import patch

import pytest

from common.path_resolver import (
    ResourceKind,
    get_artifacts_path,
    get_blob_path,
    get_raw_path,
    get_source_path,
)
from common.project_file_error import ProjectFileError
from tools.utils.project_settings import ProjectSettings


def test_get_artifacts_path_valid_project_matches_project_root_artifacts_join():
    pp = get_artifacts_path("MyProject", "docs/spec.md")
    assert pp.relative_path == "docs/spec.md"
    assert "artifacts" in os.path.normpath(pp._ProjectPath__absolute_path)
    assert pp.exists() is False


def test_get_blob_path_done_status_includes_year_subfolder():
    pp = get_blob_path("MyProject", "TD100", "done", year="2026")
    assert pp.relative_path == os.path.join("done", "2026", "TD100.md")


def test_get_blob_path_active_status_no_year_subfolder():
    pp = get_blob_path("MyProject", "TD100", "active")
    assert pp.relative_path == os.path.join("active", "TD100.md")


def test_get_blob_path_paused_status_no_year_subfolder():
    pp = get_blob_path("MyProject", "TD100", "paused")
    assert pp.relative_path == os.path.join("paused", "TD100.md")


def test_get_source_path_valid_settings_matches_source_root(tmp_path):
    mock_settings = ProjectSettings(source_root=tmp_path / "src", source_tools_available=True)
    with patch("tools.utils.project_settings.load_project_settings", return_value=mock_settings):
        pp = get_source_path("MyProject", "main.py")
        assert pp.relative_path == "main.py"
        assert os.path.normpath(pp._ProjectPath__absolute_path) == os.path.normpath(
            str(tmp_path / "src" / "main.py")
        )
        with pytest.raises(ProjectFileError):
            pp.write("test")


def test_get_source_path_missing_settings_raises_project_file_error():
    mock_settings = ProjectSettings(source_root=None, source_tools_available=False)
    with patch("tools.utils.project_settings.load_project_settings", return_value=mock_settings):
        with pytest.raises(ProjectFileError):
            get_source_path("MyProject", "main.py")


def test_get_raw_path_root_kind_returns_project_root_string():
    raw = get_raw_path("MyProject", "", kind=ResourceKind.ROOT)
    assert isinstance(raw, str)
    assert raw.endswith("MyProject")


def test_get_raw_path_artifacts_kind_returns_artifacts_root_string():
    raw = get_raw_path("MyProject", "", kind=ResourceKind.ARTIFACTS)
    assert isinstance(raw, str)
    assert raw.endswith("artifacts")


def test_get_path_project_name_with_traversal_sanitizes_project_name():
    pp = get_artifacts_path("../etc", "doc.md")
    assert "etc" in pp._ProjectPath__absolute_path
    assert ".." not in pp._ProjectPath__absolute_path


def test_get_path_relative_path_with_traversal_raises_project_file_error():
    with pytest.raises(ProjectFileError):
        get_artifacts_path("MyProject", "../../etc/passwd")
