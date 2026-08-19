import pytest
from models import WriteRequest


def test_writeRequest_patchModeNewStrOnly_resolvesToContent():
    req = WriteRequest(path="f.md", mode="patch", old_str="a", new_str="b")
    assert req.content == "b"


def test_writeRequest_patchModeBothContentAndNewStr_newStrWins():
    req = WriteRequest(path="f.md", mode="patch", old_str="a", content="c1", new_str="c2")
    assert req.content == "c2"


def test_writeRequest_patchModeContentOnlyLegacyCall_stillWorks():
    req = WriteRequest(path="f.md", mode="patch", old_str="a", content="legacy")
    assert req.content == "legacy"
    assert req.new_str is None


def test_writeRequest_replaceFileModeEmptyContent_stillRaises():
    with pytest.raises(ValueError):
        WriteRequest(path="f.md", mode="replace_file")


def test_writeRequest_explicitFieldsTracking_onlyIncludesCallerSuppliedKeys():
    req = WriteRequest(path="f.md", mode="replace_file", content="hi")
    assert "old_str" not in req.model_fields_set
    assert "start_line" not in req.model_fields_set
    assert "section_name" not in req.model_fields_set
    assert "path" in req.model_fields_set
    assert "content" in req.model_fields_set


def test_writeRequest_explicitFieldsTracking_newStrAssignmentMarksContentExplicit():
    req = WriteRequest(path="f.md", mode="patch", old_str="a", new_str="b")
    assert "content" in req.model_fields_set
