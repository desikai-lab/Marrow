"""
grammars.py — Lazy-loaded tree-sitter Language singletons.

Compatible with tree-sitter >= 0.25 (single-arg Language constructor).
Each language binary is loaded at most once per process lifetime.
Call `get_language(lang_name)` to obtain a configured Language object.
"""

from tree_sitter import Language

# Internal cache: lang_name -> Language instance
_langs: dict[str, Language] = {}


def get_language(lang_name: str) -> Language:
    """Return the tree-sitter Language for *lang_name*; load it on first call.
    Supported lang_name values: "python", "typescript", "c_sharp".
    Raises ValueError for unknown names.
    """
    if lang_name not in _langs:
        if lang_name == "python":
            import tree_sitter_python as _py  # type: ignore[import]
            _langs[lang_name] = Language(_py.language())
        elif lang_name == "typescript":
            import tree_sitter_typescript as _ts  # type: ignore[import]
            _langs[lang_name] = Language(_ts.language_typescript())
        elif lang_name == "typescript_tsx":
            import tree_sitter_typescript as _ts  # type: ignore[import]
            _langs[lang_name] = Language(_ts.language_tsx())
        elif lang_name == "c_sharp":
            import tree_sitter_c_sharp as _cs  # type: ignore[import]
            _langs[lang_name] = Language(_cs.language())
        else:
            raise ValueError(f"Unsupported language requested: {lang_name!r}")

    return _langs[lang_name]


def supported_languages() -> list[str]:
    """Return the list of language names recognised by get_language()."""
    return ["python", "typescript", "typescript_tsx", "c_sharp"]
