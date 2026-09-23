"""Tier-1 extractive keyword extraction (promoted from storage/poc/keyword_extractor.py).
Pure module: no I/O, no model calls, no lancedb/fastembed imports.
See F4000249 architecture.md §5 for extraction rules.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Protocol

from storage.artifact_chunker import ChunkInfo

_K = 20
_MAX_BYTES = 512
_STUB_MIN_TOKENS = 3
_MAX_TERM_CHARS = 64
_ACRONYM_MIN_CHARS = 2
_ACRONYM_MAX_CHARS = (
    6  # CHANGED from POC's 12 -- architecture.md §5 Priority 3: Cyrillic mitigation
)

_WORD_RE = re.compile(r"[^\W_]+")
_EDGE_RE = re.compile(r"^\W+|\W+$")
_EXT_RE = re.compile(r"\w{2,}\.[A-Za-z0-9]{1,5}$")
_HEADER_RE = re.compile(r"^#{1,3}\s")
_JOINERS = "-_.:/"
_EMPHASIS_WORDS = {"NOT", "ALWAYS", "NEVER", "MUST", "ONLY", "ALSO"}


@dataclass
class ExtractionResult:
    body: str
    kept: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    extract_ms: float = 0.0


class KeywordExtractor(Protocol):  # Tier-2 extension seam -- architecture.md §6
    """Not implemented by anything but ExtractiveKeywordExtractor in this
    feature. Exists so a future Tier-2 approach can be plugged in without
    changing the call site in tools/artifact_pipeline.py."""

    def extract_detailed(self, chunks: list[ChunkInfo]) -> list[ExtractionResult]: ...


def derive_body(chunk: ChunkInfo) -> str:
    """Drop the breadcrumb and the chunk's own header line from chunk.text.

    Markdown chunk text layout (from HeaderTreeChunkerStrategy):
        <breadcrumb>\n<own header line>\n<body...>
    Overlap chunks use 'chunk_N' sections and have no breadcrumb prefix.
    """
    prefix = chunk.section + "\n"
    if not chunk.section or not chunk.text.startswith(prefix):
        return chunk.text
    lines = chunk.text[len(prefix) :].split("\n")
    if lines and _HEADER_RE.match(lines[0]):
        lines = lines[1:]
    return "\n".join(lines)


def is_stub(body: str, min_tokens: int = _STUB_MIN_TOKENS) -> bool:
    """Return True when body has fewer than min_tokens word tokens."""
    return len(_WORD_RE.findall(body)) < min_tokens


def identifier_priority(token: str) -> int | None:
    """Return priority class (lower = higher priority), or None if not identifier-like."""
    if len(token) > _MAX_TERM_CHARS:
        return None
    letters = any(c.isalpha() for c in token)
    digits = any(c.isdigit() for c in token)
    upper = sum(1 for c in token if c.isupper())
    inner_joiner = any(c in _JOINERS for c in token[1:-1]) if len(token) > 2 else False

    if letters and digits and not inner_joiner:
        return 0
    if (
        letters
        and inner_joiner
        and (digits or upper or _EXT_RE.search(token) or "-" in token or "_" in token)
    ):
        return 1
    has_internal_upper = any(c.isupper() for c in token[1:])
    if (
        letters
        and not token.isupper()
        and not token.islower()
        and (upper >= 2 or has_internal_upper)
    ):
        return 2
    if (
        token.isalpha()
        and token.isupper()
        and _ACRONYM_MIN_CHARS <= len(token) <= _ACRONYM_MAX_CHARS
        and token not in _EMPHASIS_WORDS
    ):
        return 3
    if digits and not letters and inner_joiner and len(token) >= 5:
        return 4
    return None


def identifier_terms(body: str) -> list[str]:
    """Extract identifier-like tokens from body; case-folded, priority-ordered, deduplicated."""
    by_priority: dict[int, list[str]] = {}
    seen: set[str] = set()
    for raw in body.split():
        token = _EDGE_RE.sub("", raw)
        if not token:
            continue
        p = identifier_priority(token)
        if p is None:
            continue
        folded = token.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        by_priority.setdefault(p, []).append(folded)
    result: list[str] = []
    for p in sorted(by_priority):
        result.extend(by_priority[p])
    return result


class ExtractiveKeywordExtractor:
    """Tier-1 extractive keyword extractor.
    Promoted from storage/poc/keyword_extractor.py with Priority-3 length fix.
    """

    def extract_file(self, chunks: list[ChunkInfo]) -> list[str]:
        """Return a space-joined keyword string per chunk; '' for stubs."""
        return [" ".join(r.kept) for r in self.extract_detailed(chunks)]

    def extract_detailed(self, chunks: list[ChunkInfo]) -> list[ExtractionResult]:
        """Return an ExtractionResult per chunk with body, kept, dropped, and timing."""
        results: list[ExtractionResult] = []
        for chunk in chunks:
            t0 = time.monotonic()
            body = derive_body(chunk)
            if is_stub(body):
                results.append(ExtractionResult(body=body, kept=[], dropped=[], extract_ms=0.0))
                continue
            candidates = identifier_terms(body)
            kept: list[str] = []
            total_bytes = 0
            dropped: list[str] = []
            for term in candidates:
                tb = len(term.encode("utf-8")) + (1 if kept else 0)
                if len(kept) >= _K or total_bytes + tb > _MAX_BYTES:
                    dropped.append(term)
                    continue
                kept.append(term)
                total_bytes += tb
            results.append(
                ExtractionResult(
                    body=body,
                    kept=kept,
                    dropped=dropped,
                    extract_ms=round((time.monotonic() - t0) * 1000, 2),
                )
            )
        return results
