import logging
import os

import config
import pytest
from services import api_key_service as aks
from services.api_key_service import ApiKeyService, match_label, parse_api_keys

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


@pytest.fixture(autouse=True)
def _projects_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECTS_ROOT", str(tmp_path))


def _project(tmp_path, name="P", line=None):
    d = tmp_path / name
    d.mkdir()
    if line is not None:
        (d / ".settings").write_text(line + "\n", encoding="utf-8")
    return d


def _bump(path):  # force a new fingerprint even on coarse-mtime filesystems
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))


def test_verify_sync_valid_key_returns_label(tmp_path):
    _project(tmp_path, line=f"API_KEYS=zapier:{KEY_A},acme:{KEY_B}")
    assert ApiKeyService(max_age_s=60).verify_sync("P", KEY_B) == "acme"


@pytest.mark.parametrize("presented", [KEY_C, "", SHORT, BAD_PREFIX])
def test_verify_sync_wrong_or_malformed_key_returns_none(tmp_path, presented):
    _project(tmp_path, line=f"API_KEYS=a:{KEY_A}")
    assert ApiKeyService(max_age_s=60).verify_sync("P", presented) is None


def test_verify_sync_key_of_other_project_returns_none(tmp_path):
    _project(tmp_path, "P", f"API_KEYS=a:{KEY_A}")
    _project(tmp_path, "Q", f"API_KEYS=b:{KEY_B}")
    assert ApiKeyService(max_age_s=60).verify_sync("P", KEY_B) is None


@pytest.mark.parametrize("name", ["..", "a/b", "", "x" * 65, "missing"])
def test_verify_sync_invalid_or_unknown_project_returns_none_and_caches_nothing(tmp_path, name):
    _project(tmp_path, line=f"API_KEYS=a:{KEY_A}")
    svc = ApiKeyService(max_age_s=60)
    assert svc.verify_sync(name, KEY_A) is None and svc._cache == {}


def test_verify_sync_no_settings_file_returns_none_and_caches_nothing(tmp_path):
    _project(tmp_path)
    svc = ApiKeyService(max_age_s=60)
    assert svc.verify_sync("P", KEY_A) is None and svc._cache == {}


def test_verify_sync_settings_file_removed_revokes_keys_and_drops_cache(tmp_path):
    d = _project(tmp_path, line=f"API_KEYS=a:{KEY_A}")
    svc = ApiKeyService(max_age_s=60)
    assert svc.verify_sync("P", KEY_A) == "a"
    (d / ".settings").unlink()
    assert svc.verify_sync("P", KEY_A) is None and "P" not in svc._cache


def test_verify_sync_rotation_revokes_old_key_without_restart(tmp_path):
    d = _project(tmp_path, line=f"API_KEYS=a:{KEY_A}")
    svc = ApiKeyService(max_age_s=60)
    assert svc.verify_sync("P", KEY_A) == "a"
    (d / ".settings").write_text(f"API_KEYS=a:{KEY_B}\n", encoding="utf-8")
    _bump(d / ".settings")
    assert svc.verify_sync("P", KEY_A) is None and svc.verify_sync("P", KEY_B) == "a"


def test_verify_sync_backstop_expiry_reloads_when_fingerprint_unchanged(tmp_path, monkeypatch):
    _project(tmp_path, line=f"API_KEYS=a:{KEY_A}")
    now = [0.0]
    svc = ApiKeyService(max_age_s=60, clock=lambda: now[0])
    svc.verify_sync("P", KEY_A)
    calls, real = [], aks.read_raw_settings
    monkeypatch.setattr(aks, "read_raw_settings", lambda p: calls.append(p) or real(p))
    now[0] = 59
    svc.verify_sync("P", KEY_A)
    assert calls == []
    now[0] = 61
    svc.verify_sync("P", KEY_A)
    assert len(calls) == 1


def test_verify_sync_unreadable_settings_fails_closed(tmp_path, monkeypatch):
    _project(tmp_path, line=f"API_KEYS=a:{KEY_A}")
    monkeypatch.setattr(aks, "read_raw_settings", lambda p: {})
    assert ApiKeyService(max_age_s=60).verify_sync("P", KEY_A) is None


def test_verify_sync_compares_against_every_stored_digest(tmp_path, monkeypatch):
    _project(tmp_path, line=f"API_KEYS=a:{KEY_A},b:{KEY_B},c:{KEY_C}")
    seen, real = [], aks.hmac.compare_digest
    monkeypatch.setattr(aks.hmac, "compare_digest", lambda x, y: seen.append(1) or real(x, y))
    assert ApiKeyService(max_age_s=60).verify_sync("P", KEY_A) == "a"
    assert len(seen) == 3


def test_cache_holds_digests_only_never_plaintext_keys(tmp_path):
    _project(tmp_path, line=f"API_KEYS=a:{KEY_A}")
    svc = ApiKeyService(max_age_s=60)
    svc.verify_sync("P", KEY_A)
    assert KEY_A not in repr(svc._cache)


def test_rejected_entry_logs_one_warning_without_key(tmp_path, caplog):
    _project(tmp_path, line=f"API_KEYS=good:{KEY_A},bad:{SHORT}")
    svc = ApiKeyService(max_age_s=60)
    with caplog.at_level(logging.WARNING, logger="marrow.rest.keys"):
        svc.verify_sync("P", KEY_A)
        svc.verify_sync("P", KEY_A)
    assert len(caplog.records) == 1 and KEY_A not in caplog.text


@pytest.mark.parametrize("given,expected", [(0, 1.0), (9999, 300.0), (60, 60.0)])
def test_init_max_age_is_clamped_to_1_300(given, expected):
    assert ApiKeyService(max_age_s=given)._max_age == expected


async def test_verify_async_valid_key_returns_label(tmp_path):
    _project(tmp_path, line=f"API_KEYS=a:{KEY_A}")
    assert await ApiKeyService(max_age_s=60).verify("P", KEY_A) == "a"
