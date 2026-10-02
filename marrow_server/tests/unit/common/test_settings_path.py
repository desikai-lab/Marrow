import config
import pytest
from common.path_resolver import get_settings_path
from common.project_file_error import ProjectFileError
from tools.utils import project_settings as ps


def test_get_settings_path_valid_project_returns_settings_file_under_project_root(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(config, "PROJECTS_ROOT", str(tmp_path))
    assert get_settings_path("P") == str(tmp_path / "P" / ".settings")


@pytest.mark.parametrize("name", ["", "/", ".."])
def test_get_settings_path_invalid_project_raises_project_file_error(tmp_path, monkeypatch, name):
    monkeypatch.setattr(config, "PROJECTS_ROOT", str(tmp_path))
    with pytest.raises(ProjectFileError):
        get_settings_path(name)


def test_load_project_settings_invalid_name_returns_defaults_without_caching(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECTS_ROOT", str(tmp_path))
    ps._settings_cache.clear()
    assert ps.load_project_settings("..").source_root is None
    assert ".." not in ps._settings_cache
