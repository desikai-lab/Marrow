from storage.repositories.artifact_repository import _build_scope_filter


def test_build_scope_filter_single_scope_returns_directory_boundary_like_clause():
    result = _build_scope_filter(["docs/features/active/F4000202"])

    assert result == "(path LIKE 'docs/features/active/F4000202/%' ESCAPE '\\')"


def test_build_scope_filter_multiple_scopes_or_joins_clauses():
    result = _build_scope_filter(["docs/decisions/adr", "docs/features/active/F4000202"])

    assert result == (
        "(path LIKE 'docs/decisions/adr/%' ESCAPE '\\'"
        " OR path LIKE 'docs/features/active/F4000202/%' ESCAPE '\\')"
    )


def test_build_scope_filter_scope_with_quote_escapes_quote_as_literal_data():
    result = _build_scope_filter(["docs/o'brien"])

    assert result == "(path LIKE 'docs/o''brien/%' ESCAPE '\\')"


def test_build_scope_filter_scope_with_percent_and_underscore_escapes_wildcards():
    result = _build_scope_filter(["docs/100%_done"])

    assert result == "(path LIKE 'docs/100\\%\\_done/%' ESCAPE '\\')"


def test_build_scope_filter_scope_with_backslash_escapes_backslash_first():
    # Escaping order matters: backslash must be escaped before '%'/'_' are
    # prefixed with backslash, or a literal backslash would corrupt the pattern.
    result = _build_scope_filter(["docs\\legacy"])

    assert result == "(path LIKE 'docs\\\\legacy/%' ESCAPE '\\')"


def test_build_scope_filter_sibling_prefix_scope_produces_boundary_safe_pattern():
    # The clause itself doesn't "exclude" a sibling -- this test documents
    # the pattern shape that makes REQ-04's boundary matching possible: the
    # literal '/' immediately after the scope, which LIKE 'F40002020...'
    # cannot satisfy against a scope of 'F4000202'.
    result = _build_scope_filter(["docs/features/active/F4000202"])

    assert "F4000202/%" in result
    assert "F40002020" not in result
