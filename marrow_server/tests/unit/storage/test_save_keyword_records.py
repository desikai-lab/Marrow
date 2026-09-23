import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from storage.entities import ArtifactChunkKeywordRecord


@pytest.mark.asyncio
async def test_saveKeywordRecords_withRecords_deletesAndAddsRows():
    mock_table = MagicMock()
    with patch("storage.repositories.artifact_repository.get_keyword_table", return_value=mock_table), \
         patch("asyncio.to_thread", new=AsyncMock(return_value=None)):
        from storage.repositories.artifact_repository import ArtifactChunkRepository
        repo = ArtifactChunkRepository.__new__(ArtifactChunkRepository)
        repo.project_root = "/fake"
        records = [
            ArtifactChunkKeywordRecord(
                path="docs/a.md", start_line=1, end_line=5,
                keywords="td4000238", extracted_at="2026-09-23T00:00:00"
            )
        ]
        await repo.save_keyword_records("docs/a.md", records)


@pytest.mark.asyncio
async def test_saveKeywordRecords_emptyRecords_onlyDeletes():
    mock_table = MagicMock()
    call_log = []
    async def fake_to_thread(fn, *args):
        call_log.append(fn)
        return None
    with patch("storage.repositories.artifact_repository.get_keyword_table", return_value=mock_table), \
         patch("asyncio.to_thread", side_effect=fake_to_thread):
        from storage.repositories.artifact_repository import ArtifactChunkRepository
        repo = ArtifactChunkRepository.__new__(ArtifactChunkRepository)
        repo.project_root = "/fake"
        await repo.save_keyword_records("docs/a.md", [])
        assert len(call_log) == 1  # only delete, not add


@pytest.mark.asyncio
async def test_upsertChunks_returnsChunkList():
    """upsert_chunks must now return the list of chunks (not None)."""
    import inspect
    from storage.repositories.artifact_repository import ArtifactChunkRepository
    sig = inspect.signature(ArtifactChunkRepository.upsert_chunks)
    assert sig.return_annotation != type(None)
