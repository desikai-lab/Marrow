import os
from unittest.mock import AsyncMock

import pytest

from services.artifact_query_service import (
    _hydrate_hit_content,
    search_artifact_sections_logic,
)
from storage.db import init_db
from storage.uow import UnitOfWork
from utils.exceptions import ProjectNotFoundError

PROJECT = "content_project"
FAKE_VECTOR = [0.1] * 384  # Matches EMBEDDING_DIMENSIONS default
UPDATED = "2026-09-19T00:00:00Z"
READER = "services.artifact_query_service.read_project_artifact_logic_async"

GUIDE = "docs/guide.md"
GUIDE_TEXT = (
    "# Guide\n"  # line 1
    "\n"  # 2
    "## Alpha\n"  # 3
    "alpha line 1\n"  # 4
    "alpha line 2\n"  # 5
    "\n"  # 6
    "## Beta\n"  # 7
    "beta line 1\n"  # 8
)
# Chunker output for GUIDE_TEXT (H1 alone yields no chunk): Alpha = lines 3-6, Beta = lines 7-8.
OTHER = "docs/other.md"
OTHER_TEXT = "# Other\n\n## Only\nonly line\n"  # one chunk: lines 3-4


@pytest.fixture
def project_root(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "storage.repositories.artifact_repository.embeddings_manager.generate_vector",
        lambda *args, **kwargs: FAKE_VECTOR,
    )
    root = tmp_path / PROJECT
    (root / "artifacts" / "docs").mkdir(parents=True)
    init_db(str(root))
    return root


async def _index(root, rel_path: str, text: str) -> None:
    # write_bytes avoids CRLF translation on Windows
    (root / "artifacts" / rel_path).write_bytes(text.encode("utf-8"))
    await UnitOfWork(str(root)).chunks.upsert_chunks(rel_path, text, UPDATED, ext=".md")


def _hit(results, path: str, needle: str):
    return next(r for r in results if r.path == path and needle in r.section)


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_indexed_file_returns_live_lines_per_hit(project_root):
    await _index(project_root, GUIDE, GUIDE_TEXT)

    results = await search_artifact_sections_logic(PROJECT, "anything", limit=10)

    assert len(results) == 2
    alpha, beta = _hit(results, GUIDE, "Alpha"), _hit(results, GUIDE, "Beta")
    assert alpha.warning is None and beta.warning is None
    assert alpha.content == "## Alpha\nalpha line 1\nalpha line 2"
    assert beta.content == "## Beta\nbeta line 1"


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_include_content_false_returns_locators_only(
    project_root, monkeypatch
):
    await _index(project_root, GUIDE, GUIDE_TEXT)
    reader = AsyncMock()
    monkeypatch.setattr(READER, reader)

    results = await search_artifact_sections_logic(
        PROJECT, "anything", limit=10, include_content=False
    )

    assert len(results) == 2
    assert all(r.content is None and r.warning is None for r in results)
    reader.assert_not_called()


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_file_deleted_after_indexing_returns_warning(
    project_root,
):
    await _index(project_root, GUIDE, GUIDE_TEXT)
    os.remove(project_root / "artifacts" / GUIDE)

    results = await search_artifact_sections_logic(PROJECT, "anything", limit=10)

    assert len(results) == 2
    for r in results:
        assert r.content is None
        assert r.warning == f"Source file no longer exists at path: {GUIDE}."


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_one_file_missing_other_file_still_hydrated(
    project_root,
):
    await _index(project_root, GUIDE, GUIDE_TEXT)
    await _index(project_root, OTHER, OTHER_TEXT)
    os.remove(project_root / "artifacts" / GUIDE)

    results = await search_artifact_sections_logic(PROJECT, "anything", limit=10)

    assert len(results) == 3
    only = _hit(results, OTHER, "Only")
    assert only.content == "## Only\nonly line" and only.warning is None
    missing = [r for r in results if r.path == GUIDE]
    assert len(missing) == 2
    assert all(r.content is None and r.warning for r in missing)


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_file_shrunk_below_end_line_returns_empty_content(
    project_root,
):
    await _index(project_root, GUIDE, GUIDE_TEXT)
    (project_root / "artifacts" / GUIDE).write_bytes(b"# Guide\n")

    results = await search_artifact_sections_logic(PROJECT, "anything", limit=10)

    assert len(results) == 2
    assert all(r.content == "" and r.warning is None for r in results)


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_header_renamed_after_indexing_returns_current_text(
    project_root,
):
    await _index(project_root, GUIDE, GUIDE_TEXT)
    renamed = GUIDE_TEXT.replace("## Alpha", "## Alpha Renamed")
    (project_root / "artifacts" / GUIDE).write_bytes(renamed.encode("utf-8"))

    results = await search_artifact_sections_logic(PROJECT, "anything", limit=10)

    alpha = _hit(results, GUIDE, "Alpha")
    assert alpha.section.endswith("## Alpha")  # indexed breadcrumb is unchanged
    assert alpha.content.startswith("## Alpha Renamed")  # content is the live file


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_read_raises_returns_generic_warning_without_exception_text(
    project_root, monkeypatch
):
    await _index(project_root, GUIDE, GUIDE_TEXT)
    monkeypatch.setattr(READER, AsyncMock(side_effect=RuntimeError("boom /abs/secret/path")))

    results = await search_artifact_sections_logic(PROJECT, "anything", limit=10)

    assert len(results) == 2
    for r in results:
        assert r.content is None
        assert r.warning == f"Could not read content: {GUIDE}"
        assert "boom" not in r.warning and "secret" not in r.warning


@pytest.mark.asyncio
async def test_search_artifact_sections_logic_unknown_project_raises_project_not_found_error(
    project_root,
):
    with pytest.raises(ProjectNotFoundError):
        await search_artifact_sections_logic("no_such_project", "anything")


@pytest.mark.asyncio
async def test_hydrate_hit_content_path_escaping_artifacts_root_sets_not_resolvable_warning(
    project_root,
):
    hit = {"path": "../../escape.md", "start_line": 1, "end_line": 2}

    await _hydrate_hit_content(PROJECT, hit)

    assert hit["warning"] == "Source file no longer resolvable at path: ../../escape.md."
    assert "content" not in hit
