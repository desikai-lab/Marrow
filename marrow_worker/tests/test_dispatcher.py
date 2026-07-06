"""
tests/test_dispatcher.py — Unit tests for src/parser/dispatcher.py
"""

import pytest
from src.parser.dispatcher import get_parser_for_extension, supported_extensions
from tree_sitter import Parser

# ---------------------------------------------------------------------------
# Parametrized mapping table
# ext -> expected language name (checked via Parser internals)
# ---------------------------------------------------------------------------

SUPPORTED_EXTS = [".py", ".ts", ".tsx", ".js", ".jsx", ".cs"]


@pytest.mark.parametrize("ext", SUPPORTED_EXTS)
def test_get_parser_returns_parser(ext):
    """get_parser_for_extension() must return a tree_sitter.Parser for all known extensions."""
    parser = get_parser_for_extension(ext)
    assert isinstance(parser, Parser)


@pytest.mark.parametrize("ext", SUPPORTED_EXTS)
def test_parser_can_parse_empty_bytes(ext):
    """A parser returned for any supported extension should not crash on empty input."""
    parser = get_parser_for_extension(ext)
    tree = parser.parse(b"")
    assert tree is not None
    assert tree.root_node is not None


@pytest.mark.parametrize("ext", [".PY", ".TS", ".CS"])
def test_extension_is_case_insensitive(ext):
    """Extensions should be normalised to lowercase before lookup."""
    parser = get_parser_for_extension(ext)
    assert isinstance(parser, Parser)


# ---------------------------------------------------------------------------
# Negative cases
# ---------------------------------------------------------------------------


def test_unknown_extension_raises():
    """get_parser_for_extension() must raise ValueError for unsupported extensions."""
    with pytest.raises(ValueError, match="Unsupported file extension"):
        get_parser_for_extension(".rb")


def test_missing_dot_raises():
    """An extension without a leading dot should raise ValueError."""
    with pytest.raises(ValueError, match="Unsupported file extension"):
        get_parser_for_extension("py")


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_supported_extensions_contains_all_known():
    exts = supported_extensions()
    for ext in SUPPORTED_EXTS:
        assert ext in exts, f"Missing extension: {ext!r}"


def test_supported_extensions_sorted():
    exts = supported_extensions()
    assert exts == sorted(exts)
