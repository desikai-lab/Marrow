from unittest.mock import patch

from tools.session_context import get_guideline_logic, get_session_context_logic
from tools.source import view_file_source_logic


def test_view_file_source_logic_no_source_root_returns_string_not_raise():
    with patch("tools.source.get_source_root", return_value=None):
        result = view_file_source_logic("P", "a.py", 1, 5)
    assert result == "Project does not provide access to code files."


def test_get_guideline_logic_unknown_role_returns_error_string():
    with patch("tools.session_context.guideline_service.load", return_value="Unknown role x"):
        assert get_guideline_logic("P", "x") == "Unknown role x"


def test_get_session_context_logic_unknown_start_role_returns_error_string():
    with (
        patch("tools.artifacts.read_artifact_logic", return_value="spec"),
        patch("tools.session_context.guideline_service.load", return_value="Unknown role x"),
    ):
        assert get_session_context_logic("P", "x") == "Unknown role x"
