import pytest

from domain.responses import EmptyArtifactsResult
from services.artifact_query_service import (
    _normalize_scopes,
    _validate_scopes,
    search_artifact_sections_logic,
)
from storage.db import init_db
from storage.uow import UnitOfWork
from utils.exceptions import InvalidPathError

PROJECT = "scope_project"
FAKE_VECTOR = [0.1] * 384
UPDATED = "2026-09-20T00:00:00Z"


@pytest.fixture
def project_root(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "storage.repositories.artifact_repository.embeddings_manager.generate_vector",
        lambda *args, **kwargs: FAKE_VECTOR,
    )
    root = tmp_path / PROJECT
    (root / "artifacts").mkdir(parents=True)
    init_db(str(root))
    return root


async def _index(root, rel_path: str, text: str = "# H1\ncontent") -> None:
    full = root / "artifacts" / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(text.encode("utf-8"))
    await UnitOfWork(str(root)).chunks.upsert_chunks(rel_path, text, UPDATED, ext=".md")


# --- _normalize_scopes: pure cleanup, no I/O, no exceptions ---


def test_normalize_scopes_strips_whitespace_converts_backslash_and_drops_trailing_slash():
    assert _normalize_scopes([" docs/a/ ", "docs\\b\\c\\"]) == ["docs/a", "docs/b/c"]


def test_normalize_scopes_empty_list_returns_empty_list():
    assert _normalize_scopes([]) == []


# --- _validate_scopes: validation only, no mutation, no normalization ---


def test_validate_scopes_valid_scopes_returns_none(project_root):
    assert _validate_scopes(PROJECT, ["docs/a"]) is None


def test_validate_scopes_too_many_scopes_raises_invalid_path_error(project_root):
    with pytest.raises(InvalidPathError):
        _validate_scopes(PROJECT, [f"docs/d{i}" for i in range(21)])


def test_validate_scopes_traversal_scope_raises_invalid_path_error_without_host_path(project_root):
    with pytest.raises(InvalidPathError) as exc_info:
        _validate_scopes(PROJECT, ["../../etc"])

    assert str(project_root) not in str(exc_info.value)


def test_validate_scopes_absolute_path_scope_raises_invalid_path_error(project_root):
    with pytest.raises(InvalidPathError):
        _validate_scopes(PROJECT, ["/etc/passwd"])


def test_validate_scopes_empty_scope_string_raises_invalid_path_error(project_root):
    with pytest.raises(InvalidPathError):
        _validate_scopes(PROJECT, [""])


def test_validate_scopes_does_not_mutate_or_return_transformed_input(project_root):
    scopes = ["docs/a"]

    result = _validate_scopes(PROJECT, scopes)

    assert scopes == ["docs/a"]  # unchanged -- validation must not normalize
    assert result is None  # validation returns nothing, never a transformed list


# --- search_artifact_sections_logic: end-to-end, normalize-then-validate wired in ---


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_no_scope_behaves_identically_to_before(project_root):
    await _index(project_root, "docs/a.md")

    results = await search_artifact_sections_logic(PROJECT, "content", limit=10)

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].path == "docs/a.md"


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_single_scope_restricts_to_that_directory(
    project_root,
):
    await _index(project_root, "docs/a.md")
    await _index(project_root, "docs/features/active/F4000202/b.md")

    results = await search_artifact_sections_logic(
        PROJECT, "content", limit=10, scopes=["docs/features/active/F4000202"]
    )

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].path == "docs/features/active/F4000202/b.md"


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_multiple_scopes_or_combines_and_limit_applies_to_combined_result(
    project_root,
):
    await _index(project_root, "docs/decisions/adr/0001.md")
    await _index(project_root, "docs/features/active/F4000202/b.md")
    await _index(project_root, "sessions/history.md")

    results = await search_artifact_sections_logic(
        PROJECT,
        "content",
        limit=1,
        scopes=["docs/decisions/adr", "docs/features/active/F4000202"],
    )

    assert isinstance(results, list)
    assert (
        len(results) == 1
    )  # limit=1 fills from the 2-row in-scope OR result, not a 3-row global scan
    assert results[0].path in {"docs/decisions/adr/0001.md", "docs/features/active/F4000202/b.md"}


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_scope_with_no_matches_returns_empty_artifacts_result(
    project_root,
):
    await _index(project_root, "docs/a.md")

    result = await search_artifact_sections_logic(
        PROJECT, "content", limit=10, scopes=["docs/nonexistent"]
    )

    assert isinstance(result, EmptyArtifactsResult)
    assert "docs/nonexistent" in result.message
    assert "directories" in result.message
    assert "read_project_artifacts" in result.message


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_file_path_as_scope_returns_empty_artifacts_result_not_exception(
    project_root,
):
    await _index(project_root, "docs/a.md")

    # A caller passing a known file path as a scope: per Open Question #9
    # (resolved), this is not rejected -- it simply matches zero chunks and
    # falls through to the REQ-07 EmptyArtifactsResult, whose message tells
    # the caller scopes are directories.
    result = await search_artifact_sections_logic(
        PROJECT, "content", limit=10, scopes=["docs/a.md"]
    )

    assert isinstance(result, EmptyArtifactsResult)
    assert "directories" in result.message


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_traversal_scope_raises_invalid_path_error_without_host_path(
    project_root,
):
    with pytest.raises(InvalidPathError) as exc_info:
        await search_artifact_sections_logic(PROJECT, "content", limit=10, scopes=["../../etc"])

    message = str(exc_info.value)
    assert str(project_root) not in message  # REQ-05: no host path leak


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_absolute_path_scope_raises_invalid_path_error(
    project_root,
):
    with pytest.raises(InvalidPathError):
        await search_artifact_sections_logic(PROJECT, "content", limit=10, scopes=["/etc/passwd"])


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_too_many_scopes_raises_invalid_path_error(
    project_root,
):
    with pytest.raises(InvalidPathError):
        await search_artifact_sections_logic(
            PROJECT, "content", limit=10, scopes=[f"docs/d{i}" for i in range(21)]
        )


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_whitespace_only_scope_raises_invalid_path_error(
    project_root,
):
    # Exercises the full pipeline: normalize collapses "   " to "", validate
    # then rejects the empty string. (Direct unit tests above cover each
    # function; this covers them wired together.)
    with pytest.raises(InvalidPathError):
        await search_artifact_sections_logic(PROJECT, "content", limit=10, scopes=["   "])


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_none_scopes_is_unscoped(project_root):
    await _index(project_root, "docs/a.md")

    results = await search_artifact_sections_logic(PROJECT, "content", limit=10, scopes=None)

    assert isinstance(results, list)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_empty_list_scopes_is_unscoped(project_root):
    await _index(project_root, "docs/a.md")

    results = await search_artifact_sections_logic(PROJECT, "content", limit=10, scopes=[])

    assert isinstance(results, list)
    assert len(results) == 1
