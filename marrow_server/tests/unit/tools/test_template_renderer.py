from unittest.mock import MagicMock

import pytest
from tools.utils.template_renderer import TemplateRenderer


def test_render_singlePlaceholder_returnsSubstituted():
    mock_context = MagicMock()
    mock_context.variables = {"KEY": "VALUE"}
    content = "Hello {{KEY}}!"
    result = TemplateRenderer.render(content, mock_context)
    assert result == "Hello VALUE!"


def test_render_missingKey_leavesPlaceholderAndWarns():
    mock_context = MagicMock()
    mock_context.variables = {}
    content = "Hello {{MISSING}}!"
    with pytest.warns(UserWarning, match="Unresolved placeholder '{{MISSING}}'"):
        result = TemplateRenderer.render(content, mock_context)
    assert result == "Hello {{MISSING}}!"


def test_render_keyLookupIsCaseInsensitive():
    mock_context = MagicMock()
    mock_context.variables = {"KEY": "VALUE"}
    content = "Hello {{key}}!"
    result = TemplateRenderer.render(content, mock_context)
    assert result == "Hello VALUE!"


def test_render_noPlaceholders_returnsOriginal():
    mock_context = MagicMock()
    mock_context.variables = {"KEY": "VALUE"}
    content = "Hello World!"
    result = TemplateRenderer.render(content, mock_context)
    assert result == "Hello World!"


def test_render_multiplePlaceholders_allSubstituted():
    mock_context = MagicMock()
    mock_context.variables = {"A": "1", "B": "2"}
    content = "{{A}} + {{B}} = 3"
    result = TemplateRenderer.render(content, mock_context)
    assert result == "1 + 2 = 3"
