from tools.utils import project_settings as ps


def test_read_raw_settings_valid_file_returns_dict_without_touching_cache(tmp_path):
    f = tmp_path / ".settings"
    f.write_text("# c\nAPI_KEYS=a:b\nSOURCE_ROOT=/x\n", encoding="utf-8")
    before = dict(ps._settings_cache)
    assert ps.read_raw_settings(f) == {"API_KEYS": "a:b", "SOURCE_ROOT": "/x"}
    assert ps._settings_cache == before


def test_read_raw_settings_missing_file_returns_empty_dict(tmp_path):
    assert ps.read_raw_settings(tmp_path / ".settings") == {}
