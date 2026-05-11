"""
dispatcher.py — Parser Factory.

Maps file extensions to the correct tree-sitter Parser+Language pair
using a static strategy map instead of if-elif chains.
Compatible with tree-sitter >= 0.25 (Parser takes Language in constructor).
"""

from tree_sitter import Parser

from .grammars import get_language

# Extension → language name strategy map
_LANG_MAP: dict[str, str] = {
    ".py":  "python",
    ".ts":  "typescript",
    ".tsx": "typescript_tsx",   # uses language_tsx() — supports JSX syntax
    ".js":  "typescript",
    ".jsx": "typescript_tsx",   # JSX is also TSX grammar
    ".cs":  "c_sharp",
}


def get_parser_for_extension(file_ext: str) -> Parser:
    """Return a configured tree-sitter Parser for the given file extension.

    Args:
        file_ext: A file extension including the leading dot, e.g. '.py', '.ts'.

    Returns:
        A ``tree_sitter.Parser`` instance pre-set to the appropriate language.

    Raises:
        ValueError: If the extension is not mapped to a supported language.
    """
    ext = file_ext.lower()
    lang_name = _LANG_MAP.get(ext)
    if not lang_name:
        raise ValueError(
            f"Unsupported file extension: {ext!r}. "
            f"Supported: {sorted(_LANG_MAP.keys())}"
        )

    # tree-sitter >= 0.25: Language is passed directly to Parser constructor
    return Parser(get_language(lang_name))


def supported_extensions() -> list[str]:
    """Return all file extensions handled by the dispatcher."""
    return sorted(_LANG_MAP.keys())
