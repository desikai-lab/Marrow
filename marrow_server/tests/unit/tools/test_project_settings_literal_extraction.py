from pathlib import Path
from unittest.mock import mock_open, patch

from tools.utils.project_settings import load_project_settings


def _clear_cache():
    from tools.utils import project_settings as ps

    ps._settings_cache.clear()


def test_literalExtraction_defaultOff_whenNoSettingsFile():
    _clear_cache()
    with patch("tools.utils.project_settings.Path.exists", return_value=False):
        settings = load_project_settings("TestProject")
    assert settings.literal_extraction is False


def test_literalExtraction_parsedTrue_whenFlagSetOn():
    _clear_cache()
    fake_settings = "SOURCE_ROOT=/projects/Marrow\nLITERAL_EXTRACTION=on\n"
    with (
        patch("tools.utils.project_settings.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=fake_settings)),
        patch("pathlib.Path.read_text", return_value=fake_settings),
        patch("pathlib.Path.resolve", return_value=Path("/projects/Marrow")),
        patch("pathlib.Path.is_dir", return_value=True),
    ):
        settings = load_project_settings("TestProject")
    assert settings.literal_extraction is True


def test_literalExtraction_remainsFalse_whenFlagAbsent():
    _clear_cache()
    fake_settings = "SOURCE_ROOT=/projects/Marrow\n"
    with (
        patch("tools.utils.project_settings.Path.exists", return_value=True),
        patch("pathlib.Path.read_text", return_value=fake_settings),
        patch("pathlib.Path.resolve", return_value=Path("/projects/Marrow")),
        patch("pathlib.Path.is_dir", return_value=True),
    ):
        settings = load_project_settings("TestProject")
    assert settings.literal_extraction is False
