"""Per-project REST API keys (ADR-0053 sections 5-8). No FastAPI imports."""

import hashlib
import hmac
import logging
import re
from collections import Counter
from dataclasses import dataclass

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
