"""Per-project REST API keys (ADR-0053 sections 5-8). No FastAPI imports."""

import asyncio
import hashlib
import hmac
import logging
import re
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import config
from common.path_resolver import get_settings_path
from common.project_file_error import ProjectFileError
from tools.utils.project_settings import read_raw_settings

logger = logging.getLogger("marrow.rest.keys")

PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
KEY_RE = re.compile(r"^mk_[A-Za-z0-9_-]{32,128}$")
_DUMMY_DIGEST = hashlib.sha256(b"marrow-rest-dummy").digest()


@dataclass(frozen=True)
class KeyEntry:
    label: str
    digest: bytes


def _digest(key: str) -> bytes:
    return hashlib.sha256(key.encode("utf-8")).digest()


def _parse_pair(position: int, item: str) -> tuple[str, str] | str:
    """Return (label, key) or a reason string. Reasons never contain key material."""
    label, sep, key = item.strip().partition(":")
    label, key = label.strip(), key.strip()
    if not sep:
        return f"entry #{position}: missing colon separator"
    if not label or not key:
        return f"entry #{position}: empty label or key"
    if not LABEL_RE.match(label):
        return f"entry #{position}: invalid label"
    if not KEY_RE.match(key):
        return f"entry {label!r}: key must be mk_ plus 32-128 url-safe characters"
    return label, key


def _drop_duplicates(pairs: list[tuple[str, str]], warnings: list[str]) -> list[KeyEntry]:
    labels = Counter(label for label, _ in pairs)
    keys = Counter(key for _, key in pairs)
    kept: list[KeyEntry] = []
    for label, key in pairs:
        if labels[label] > 1:
            warnings.append(f"entry {label!r}: duplicate label rejected")
        elif keys[key] > 1:
            warnings.append(f"entry {label!r}: duplicate key value rejected")
        else:
            kept.append(KeyEntry(label, _digest(key)))
    return kept


def parse_api_keys(raw: str | None) -> tuple[list[KeyEntry], list[str]]:
    if not raw or not raw.strip():
        return [], []
    warnings: list[str] = []
    pairs: list[tuple[str, str]] = []
    for position, item in enumerate(raw.split(","), start=1):
        parsed = _parse_pair(position, item)
        if isinstance(parsed, str):
            warnings.append(parsed)
        else:
            pairs.append(parsed)
    return _drop_duplicates(pairs, warnings), warnings


def match_label(entries, presented: str) -> str | None:
    """Constant-work comparison against EVERY stored digest (no early exit)."""
    digest = _digest(presented)
    matched: str | None = None
    for entry in entries:
        if hmac.compare_digest(entry.digest, digest):
            matched = entry.label
    if not entries:
        hmac.compare_digest(_DUMMY_DIGEST, digest)
    return matched


EMPTY_TTL_S = 5.0


@dataclass(frozen=True)
class _Cached:
    fingerprint: tuple[int, int, int]
    loaded_at: float
    entries: tuple[KeyEntry, ...]


def _fingerprint(path: Path) -> tuple[int, int, int] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size, st.st_ino)


def _settings_file(project: str) -> Path | None:
    try:
        return Path(get_settings_path(project))
    except ProjectFileError:
        return None


class ApiKeyService:
    def __init__(
        self,
        max_age_s: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        age = max_age_s if max_age_s is not None else config.REST_KEY_CACHE_MAX_AGE_S
        self._max_age = min(max(float(age), 1.0), 300.0)
        self._clock = clock
        self._cache: dict[str, _Cached] = {}

    async def verify(self, project: str, presented: str) -> str | None:
        return await asyncio.to_thread(self.verify_sync, project, presented)

    def verify_sync(self, project: str, presented: str) -> str | None:
        entries = self._entries_for(project) if PROJECT_RE.match(project or "") else ()
        candidate = presented if KEY_RE.match(presented or "") else ""
        return match_label(entries, candidate)

    def _ttl(self, cached: _Cached) -> float:
        return self._max_age if cached.entries else EMPTY_TTL_S

    def _entries_for(self, project: str) -> tuple[KeyEntry, ...]:
        path = _settings_file(project)
        fingerprint = _fingerprint(path) if path is not None else None
        if fingerprint is None:  # unknown project or no .settings: no keys, nothing cached
            self._cache.pop(project, None)
            return ()
        now = self._clock()
        cached = self._cache.get(project)
        fresh = cached and now - cached.loaded_at < self._ttl(cached)
        if cached and fresh and cached.fingerprint == fingerprint:
            return cached.entries
        changed = cached is None or cached.fingerprint != fingerprint
        entries = self._load(project, path, log=changed)
        self._cache[project] = _Cached(fingerprint, now, entries)
        return entries

    def _load(self, project: str, path: Path, log: bool) -> tuple[KeyEntry, ...]:
        entries, warnings = parse_api_keys(read_raw_settings(path).get("API_KEYS"))
        if log:
            for reason in warnings:
                logger.warning("[REST][Keys] project=%s API_KEYS %s", project, reason)
        return tuple(entries)


_service: ApiKeyService | None = None


def get_api_key_service() -> ApiKeyService:
    global _service
    if _service is None:
        _service = ApiKeyService()
    return _service


def reset_api_key_service() -> None:
    global _service
    _service = None
