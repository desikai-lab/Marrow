from unittest.mock import MagicMock, patch

import pytest


def _settings(literal_extraction: bool) -> MagicMock:
    s = MagicMock()
    s.literal_extraction = literal_extraction
    return s


@pytest.mark.asyncio
async def test_maybeExtractKeywords_flagOff_doesNothing():
    with patch("storage.keyword_extractor.ExtractiveKeywordExtractor") as mock_extractor:
        from tools.artifact_pipeline import maybe_extract_keywords

        await maybe_extract_keywords(
            _settings(False), MagicMock(), "docs/a.md", [MagicMock()], "2026"
        )
        mock_extractor.assert_not_called()


@pytest.mark.asyncio
async def test_maybeExtractKeywords_extractorRaises_doesNotPropagate():
    with patch(
        "storage.keyword_extractor.ExtractiveKeywordExtractor", side_effect=RuntimeError("boom")
    ):
        from tools.artifact_pipeline import maybe_extract_keywords

        await maybe_extract_keywords(
            _settings(True), MagicMock(), "docs/a.md", [MagicMock()], "2026"
        )


@pytest.mark.asyncio
async def test_maybeExtractKeywords_emptyChunks_doesNothing():
    with patch("storage.keyword_extractor.ExtractiveKeywordExtractor") as mock_extractor:
        from tools.artifact_pipeline import maybe_extract_keywords

        await maybe_extract_keywords(_settings(True), MagicMock(), "docs/a.md", [], "2026")
        mock_extractor.assert_not_called()


@pytest.mark.asyncio
async def test_maybeExtractKeywords_flagOn_savesRecordsViaChunkRepo():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    chunk = SimpleNamespace(
        text="TD4000238 is blocked by F4000249 today", section="", start_line=1, end_line=5
    )
    repo = MagicMock()
    repo.save_keyword_records = AsyncMock()
    from tools.artifact_pipeline import maybe_extract_keywords

    await maybe_extract_keywords(_settings(True), repo, "docs/a.md", [chunk], "2026")
    repo.save_keyword_records.assert_awaited_once()
    path_arg, records = repo.save_keyword_records.await_args.args
    assert path_arg == "docs/a.md"
    assert records[0].start_line == 1 and records[0].end_line == 5
    assert "td4000238" in records[0].keywords
