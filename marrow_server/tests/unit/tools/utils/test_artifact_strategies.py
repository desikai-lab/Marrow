import pytest
from tools.utils.artifact_strategies import (
    AppendSectionStrategy,
    DeleteSectionStrategy,
    PatchStrategy,
    ReplaceChunkStrategy,
    ReplaceFileStrategy,
    ReplaceSectionStrategy,
    find_unknown_fields,
)


def test_findUnknownFields_replaceFileWithOldStr_returnsWarning():
    strategy = ReplaceFileStrategy()
    warning = find_unknown_fields(strategy, {"path", "content", "mode", "old_str"})
    assert warning == "Field(s) 'old_str' are not used by write mode 'replace_file' and were ignored."


def test_findUnknownFields_patchWithOnlyAllowedFields_returnsNone():
    strategy = PatchStrategy()
    warning = find_unknown_fields(strategy, {"path", "content", "mode", "old_str"})
    assert warning is None


def test_findUnknownFields_patchWithNewStr_returnsNone():
    strategy = PatchStrategy()
    warning = find_unknown_fields(strategy, {"path", "new_str", "mode", "old_str"})
    assert warning is None


def test_findUnknownFields_appendSectionWithStartLine_returnsWarning():
    strategy = AppendSectionStrategy()
    warning = find_unknown_fields(strategy, {"path", "content", "mode", "section_name", "start_line"})
    assert warning == "Field(s) 'start_line' are not used by write mode 'append_section' and were ignored."


def test_findUnknownFields_replaceSectionWithOldStr_returnsWarning():
    strategy = ReplaceSectionStrategy()
    warning = find_unknown_fields(strategy, {"path", "content", "mode", "section_name", "old_str"})
    assert warning == "Field(s) 'old_str' are not used by write mode 'replace_section' and were ignored."


def test_findUnknownFields_replaceChunkWithSectionName_returnsWarning():
    strategy = ReplaceChunkStrategy()
    warning = find_unknown_fields(
        strategy, {"path", "content", "mode", "start_line", "end_line", "section_name"}
    )
    assert warning == "Field(s) 'section_name' are not used by write mode 'replace_chunk' and were ignored."


def test_findUnknownFields_deleteSectionWithContent_returnsWarning():
    strategy = DeleteSectionStrategy()
    warning = find_unknown_fields(strategy, {"path", "content", "mode", "section_name"})
    assert warning == "Field(s) 'content' are not used by write mode 'delete_section' and were ignored."


def test_findUnknownFields_emptyExplicitFields_returnsNone():
    strategy = ReplaceFileStrategy()
    warning = find_unknown_fields(strategy, set())
    assert warning is None
