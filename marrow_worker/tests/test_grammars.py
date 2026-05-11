"""
tests/test_grammars.py — Unit tests for src/parser/grammars.py
"""

import pytest
from tree_sitter import Language

from src.parser.grammars import get_language, supported_languages

# ---------------------------------------------------------------------------
# Positive cases: every supported language loads
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang_name", supported_languages())
def test_get_language_returns_language_object(lang_name):
    """get_language() must return a tree_sitter.Language for every supported name."""
    lang = get_language(lang_name)
    assert isinstance(lang, Language)


@pytest.mark.parametrize("lang_name", supported_languages())
def test_get_language_is_singleton(lang_name):
    """Calling get_language() twice returns the exact same object (singleton)."""
    lang1 = get_language(lang_name)
    lang2 = get_language(lang_name)
    assert lang1 is lang2


# ---------------------------------------------------------------------------
# Negative cases
# ---------------------------------------------------------------------------


def test_get_language_raises_on_unknown():
    """get_language() must raise ValueError for an unknown language name."""
    with pytest.raises(ValueError, match="Unsupported language"):
        get_language("cobol")


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_supported_languages_returns_list():
    langs = supported_languages()
    assert isinstance(langs, list)
    assert len(langs) >= 4  # python, typescript, typescript_tsx, c_sharp


def test_supported_languages_contains_expected():
    langs = supported_languages()
    for expected in ("python", "typescript", "typescript_tsx", "c_sharp"):
        assert expected in langs, f"Missing expected language: {expected!r}"
