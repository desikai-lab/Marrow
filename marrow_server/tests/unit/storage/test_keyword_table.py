from unittest.mock import MagicMock, patch

from storage.entities import ArtifactChunkKeywordRecord


def test_artifactChunkKeywordRecord_toIndexRow_returnsAllFields():
    record = ArtifactChunkKeywordRecord(
        path="docs/spec.md",
        start_line=10,
        end_line=20,
        keywords="td4000238 memgpt",
        extracted_at="2026-09-23T12:00:00",
    )
    row = record.to_index_row()
    assert row["path"] == "docs/spec.md"
    assert row["start_line"] == 10
    assert row["end_line"] == 20
    assert row["keywords"] == "td4000238 memgpt"
    assert row["extracted_at"] == "2026-09-23T12:00:00"


def test_artifactChunkKeywordRecord_emptyKeywords_allowedForStubs():
    record = ArtifactChunkKeywordRecord(
        path="docs/spec.md",
        start_line=1,
        end_line=1,
        keywords="",
        extracted_at="2026-09-23T12:00:00",
    )
    assert record.to_index_row()["keywords"] == ""


@patch("storage.db.get_db")
@patch("storage.db.list_table_names", return_value=[])
def test_getKeywordTable_tableNotExists_createsTable(mock_list, mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    from storage.db import get_keyword_table

    get_keyword_table("/fake/root")
    mock_db.create_table.assert_called_once()
    args, kwargs = mock_db.create_table.call_args
    assert args[0] == "artifact_chunk_keywords"
    assert kwargs.get("exist_ok") is True


@patch("storage.db.get_db")
@patch("storage.db.list_table_names", return_value=["artifact_chunk_keywords"])
def test_getKeywordTable_tableExists_opensTable(mock_list, mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    from storage.db import get_keyword_table

    get_keyword_table("/fake/root")
    mock_db.open_table.assert_called_once_with("artifact_chunk_keywords")
