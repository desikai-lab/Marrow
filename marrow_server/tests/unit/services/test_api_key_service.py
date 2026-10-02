import pytest
from services.api_key_service import match_label, parse_api_keys

KEY_A = "mk_" + "A" * 43
KEY_B = "mk_" + "B" * 43
KEY_C = "mk_" + "C" * 43
SHORT = "mk_short"
BAD_PREFIX = "xx_" + "A" * 43


def test_parse_api_keys_two_valid_entries_returns_both_labels():
    entries, warnings = parse_api_keys(f"zapier:{KEY_A}, acme:{KEY_B}")
    assert [e.label for e in entries] == ["zapier", "acme"] and warnings == []


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_parse_api_keys_empty_input_returns_nothing(raw):
    assert parse_api_keys(raw) == ([], [])


@pytest.mark.parametrize(
    "item",
    [
        KEY_A,
        f":{KEY_A}",
        "zap:",
        f"-bad:{KEY_A}",
        f"zap:{SHORT}",
        f"zap:{BAD_PREFIX}",
        f"zap:{KEY_A}:x",
        "",
    ],
)
def test_parse_api_keys_malformed_entry_dropped_with_one_warning(item):
    entries, warnings = parse_api_keys(f"good:{KEY_B},{item}")
    assert [e.label for e in entries] == ["good"] and len(warnings) == 1


def test_parse_api_keys_duplicate_label_rejects_every_entry_with_that_label():
    entries, warnings = parse_api_keys(f"a:{KEY_A},a:{KEY_B},c:{KEY_C}")
    assert [e.label for e in entries] == ["c"] and len(warnings) == 2


def test_parse_api_keys_duplicate_key_value_rejects_both_entries():
    entries, _ = parse_api_keys(f"a:{KEY_A},b:{KEY_A},c:{KEY_C}")
    assert [e.label for e in entries] == ["c"]


def test_parse_api_keys_warnings_never_contain_key_material():
    _, warnings = parse_api_keys(f"a:{KEY_A},a:{KEY_B},zap:{SHORT},x:{KEY_C}:y")
    assert not any(k in w for w in warnings for k in (KEY_A, KEY_B, KEY_C))


def test_match_label_valid_key_returns_label_and_wrong_key_returns_none():
    entries, _ = parse_api_keys(f"a:{KEY_A},b:{KEY_B}")
    assert match_label(entries, KEY_B) == "b" and match_label(entries, KEY_C) is None


def test_match_label_no_entries_returns_none():
    assert match_label([], KEY_A) is None
