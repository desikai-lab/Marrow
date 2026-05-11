import re
from typing import List, Tuple


def build_fenced_ranges(content: str) -> List[Tuple[int, int]]:
    """
    Returns a list of character ranges (start, end) for fenced code blocks
    (``` or ~~~) in Markdown text.

    Used to skip # headings inside code blocks when parsing sections.
    Referenced by artifact_chunker.py and build_processors.py.
    """
    fenced_ranges: List[Tuple[int, int]] = []
    fence_pattern = re.compile(r"^(`{3,}|~{3,})", re.MULTILINE)
    fences = list(fence_pattern.finditer(content))

    i = 0
    while i < len(fences) - 1:
        open_f = fences[i]
        marker = open_f.group(1)
        # The closing marker must be the same length or longer
        close_p = re.compile(
            rf"^{re.escape(marker[0])}{{{len(marker)},}}\s*$", re.MULTILINE
        )
        close_f = close_p.search(content, open_f.end())
        if close_f:
            fenced_ranges.append((open_f.start(), close_f.end()))
            # Skip all markers nested inside this block
            while i + 1 < len(fences) and fences[i + 1].start() < close_f.end():
                i += 1
        i += 1

    return fenced_ranges


def in_fenced_range(pos: int, fenced_ranges: List[Tuple[int, int]]) -> bool:
    """Returns True if the character position falls inside a fenced code block."""
    return any(s <= pos < e for s, e in fenced_ranges)
