import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass

from config import DEFAULT_CHUNK_OVERLAP_PCT
from tools.utils.markdown_fence import build_fenced_ranges, in_fenced_range


@dataclass
class ChunkInfo:
    section: str
    start_line: int
    end_line: int
    text: str


class ChunkerStrategy(ABC):
    @abstractmethod
    def chunk(
        self, content: str, max_chars: int, overlap_pct: float | None = None
    ) -> Iterator[ChunkInfo]:
        """Generates chunks from content. max_chars is primarily used for text files.
        overlap_pct is only meaningful to OverlapChunkerStrategy; structured
        strategies accept and ignore it for call-site uniformity."""
        pass


class HeaderTreeChunkerStrategy(ChunkerStrategy):
    """Structured strategy: builds an H1->H2->H3 breadcrumb per leaf chunk."""

    HEADER_PATTERN = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

    def chunk(
        self, content: str, max_chars: int, overlap_pct: float | None = None
    ) -> Iterator[ChunkInfo]:
        fenced_ranges = build_fenced_ranges(content)
        headers = self._find_all_headers(content, fenced_ranges)

        if not self._has_splittable_structure(headers):
            yield from OverlapChunkerStrategy().chunk(
                content, max_chars, overlap_pct=overlap_pct
            )
            return

        lines = content.split("\n")
        split_points = list(self._build_breadcrumb_stack(headers))

        for i, (header_match, stack) in enumerate(split_points):
            start_pos = header_match.start()
            start_line = content[:start_pos].count("\n") + 1
            end_pos = split_points[i + 1][0].start() if i + 1 < len(split_points) else len(content)
            end_line = content[:end_pos].count("\n") if i + 1 < len(split_points) else len(lines)
            body = content[start_pos:end_pos].strip()

            breadcrumb = self._breadcrumb_str(stack)
            yield ChunkInfo(
                section=breadcrumb,
                start_line=start_line,
                end_line=end_line,
                text=f"{breadcrumb}\n{body}",
            )

    def _find_all_headers(self, content, fenced_ranges):
        return [
            m
            for m in self.HEADER_PATTERN.finditer(content)
            if not in_fenced_range(m.start(), fenced_ranges)
        ]

    def _has_splittable_structure(self, headers) -> bool:
        return any(len(m.group(1)) in (2, 3) for m in headers)

    def _build_breadcrumb_stack(self, headers):
        stack = [None, None, None]  # h1, h2, h3
        for m in headers:
            level = len(m.group(1))
            text = m.group(0).strip()
            if level == 1:
                stack = [text, None, None]
                continue
            if level == 2:
                stack[1], stack[2] = text, None
            elif level == 3:
                if stack[1] is None:
                    yield m, self._orphan_h3_parent(stack, text)
                    continue
                stack[2] = text
            yield m, list(stack)

    def _breadcrumb_str(self, stack) -> str:
        return " > ".join(part for part in stack if part)

    def _orphan_h3_parent(self, stack, h3_text) -> list[str | None]:
        return [stack[0], None, h3_text]


class OverlapChunkerStrategy(ChunkerStrategy):
    """Unstructured strategy: fixed-size sliding windows with configurable overlap."""

    def chunk(
        self, content: str, max_chars: int, overlap_pct: float | None = None
    ) -> Iterator[ChunkInfo]:
        if not content.strip():
            return

        pct = overlap_pct if overlap_pct is not None else DEFAULT_CHUNK_OVERLAP_PCT
        overlap_chars = self._resolve_overlap_chars(pct, max_chars)

        if len(content) <= max_chars:
            yield ChunkInfo(
                section="chunk_1",
                start_line=1,
                end_line=self._get_line_count(content),
                text=content,
            )
            return

        pos = 0
        chunk_index = 1
        while pos < len(content):
            raw_end = min(pos + max_chars, len(content))
            end = (
                self._next_window_end(content, raw_end, max_chars)
                if raw_end < len(content)
                else raw_end
            )
            window = content[pos:end]

            start_line = content[:pos].count("\n") + 1
            end_line = content[:end].count("\n") + 1
            yield ChunkInfo(
                section=f"chunk_{chunk_index}",
                start_line=start_line,
                end_line=end_line,
                text=window,
            )

            if end >= len(content):
                break
            pos = max(end - overlap_chars, pos + 1)  # guard: always advance at least 1 char
            chunk_index += 1

    def _resolve_overlap_chars(self, overlap_pct: float, max_chars: int) -> int:
        return int(max_chars * overlap_pct)

    def _next_window_end(self, content: str, raw_end: int, max_chars: int) -> int:
        return self._snap_to_boundary(content, raw_end)

    def _snap_to_boundary(self, content: str, raw_end: int, lookback: int = 40) -> int:
        window_start = max(0, raw_end - lookback)
        segment = content[window_start:raw_end]
        idx = segment.rfind(" ")
        if idx == -1:
            idx = segment.rfind("\n")
        return window_start + idx if idx != -1 else raw_end

    @staticmethod
    def _get_line_count(text: str) -> int:
        return text.count("\n") + 1 if text else 0


class ChunkerFactory:
    STRUCTURED_EXTENSIONS = {".md"}

    @classmethod
    def get(cls, ext: str) -> ChunkerStrategy:
        if ext.lower() in cls.STRUCTURED_EXTENSIONS:
            return HeaderTreeChunkerStrategy()
        return OverlapChunkerStrategy()
