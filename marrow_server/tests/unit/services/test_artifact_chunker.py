"""Unit tests for storage.artifact_chunker (ASV-9).

Covers:
- MarkdownChunker: basic heading split, fence-awareness, no-headers fallback
- TextChunker: paragraph splitting, max_chars boundary, empty content guard
- ChunkerFactory: extension routing
- tools.utils.markdown_fence: build_fenced_ranges / in_fenced_range helpers
"""
import pytest
from storage.artifact_chunker import (
    ChunkInfo,
    ChunkerFactory,
    MarkdownChunker,
    TextChunker,
)
from tools.utils.markdown_fence import build_fenced_ranges, in_fenced_range


# ---------------------------------------------------------------------------
# markdown_fence helpers
# ---------------------------------------------------------------------------

class TestBuildFencedRanges:
    def test_build_fenced_ranges_empty_content_returns_empty_list(self):
        assert build_fenced_ranges("") == []

    def test_build_fenced_ranges_no_fences_returns_empty_list(self):
        assert build_fenced_ranges("Just some text.\n## Header") == []

    def test_build_fenced_ranges_single_block_returns_one_range(self):
        content = "before\n```\ncode\n```\nafter"
        ranges = build_fenced_ranges(content)
        assert len(ranges) == 1
        start, end = ranges[0]
        # The opening ``` must be inside the range
        assert content[start:start+3] == "```"

    def test_build_fenced_ranges_tilde_block_returns_one_range(self):
        content = "~~~\nsome code\n~~~"
        ranges = build_fenced_ranges(content)
        assert len(ranges) == 1

    def test_build_fenced_ranges_nested_markers_returns_one_range(self):
        """Markers inside a block must not start a new range."""
        content = "```\nouter\n```python\ninner\n```\n```"
        ranges = build_fenced_ranges(content)
        # Only the outermost pair should be matched
        assert len(ranges) == 1

    def test_build_fenced_ranges_two_blocks_returns_two_ranges(self):
        content = "```\nblock1\n```\n\nsome text\n\n```\nblock2\n```"
        ranges = build_fenced_ranges(content)
        assert len(ranges) == 2


class TestInFencedRange:
    def test_in_fenced_range_position_before_returns_false(self):
        ranges = [(10, 20)]
        assert not in_fenced_range(5, ranges)

    def test_in_fenced_range_position_at_start_returns_true(self):
        ranges = [(10, 20)]
        assert in_fenced_range(10, ranges)

    def test_in_fenced_range_position_inside_returns_true(self):
        ranges = [(10, 20)]
        assert in_fenced_range(15, ranges)

    def test_in_fenced_range_position_at_end_returns_false(self):
        """End is exclusive — position == end should NOT be inside."""
        ranges = [(10, 20)]
        assert not in_fenced_range(20, ranges)

    def test_in_fenced_range_empty_ranges_returns_false(self):
        assert not in_fenced_range(5, [])


# ---------------------------------------------------------------------------
# MarkdownChunker
# ---------------------------------------------------------------------------

class TestMarkdownChunker:
    def _chunk(self, content: str, max_chars: int = 5000):
        return list(MarkdownChunker().chunk(content, max_chars))

    def test_chunk_basic_h2_split_returns_multiple_chunks(self):
        content = (
            "# Document Title\n"
            "Intro paragraph.\n"
            "## Step 1\n"
            "Do the first thing.\n"
            "## Step 2\n"
            "Do the second thing.\n"
        )
        chunks = self._chunk(content)
        assert len(chunks) == 2
        assert chunks[0].section == "## Step 1"
        assert chunks[1].section == "## Step 2"
        assert "first thing" in chunks[0].text
        assert "second thing" in chunks[1].text

    def test_chunk_h3_split_returns_separate_chunks(self):
        content = (
            "## Section A\n"
            "Intro.\n"
            "### Sub-section A.1\n"
            "Detail.\n"
            "## Section B\n"
            "More.\n"
        )
        chunks = self._chunk(content)
        assert len(chunks) == 3
        assert chunks[0].section == "## Section A"
        assert chunks[1].section == "### Sub-section A.1"
        assert chunks[2].section == "## Section B"

    def test_chunk_headings_in_fences_returns_ignored_chunks(self):
        content = (
            "## Real Header\n"
            "```python\n"
            "# This comment looks like a heading\n"
            "## not a heading\n"
            "```\n"
            "### Genuine Sub\n"
            "Text.\n"
        )
        chunks = self._chunk(content)
        assert len(chunks) == 2
        assert chunks[0].section == "## Real Header"
        assert chunks[1].section == "### Genuine Sub"

    def test_chunk_no_headings_returns_root_chunk(self):
        """Without any ## / ### headers the entire content is returned as a single root chunk."""
        content = "Just a flat document.\n\nNo headings anywhere."
        chunks = self._chunk(content)
        assert len(chunks) == 1
        assert chunks[0].section == "(root)"

    def test_chunk_empty_content_returns_empty_list(self):
        chunks = self._chunk("")
        assert chunks == []

    def test_chunk_content_returns_1_based_line_numbers(self):
        content = "## Alpha\nLine two.\n## Beta\nLine four.\n"
        chunks = self._chunk(content)
        assert chunks[0].start_line >= 1
        assert chunks[1].start_line > chunks[0].start_line

    def test_chunk_content_returns_chunk_with_header(self):
        content = "## My Section\nSome content here.\n"
        chunks = self._chunk(content)
        assert "## My Section" in chunks[0].text


# ---------------------------------------------------------------------------
# TextChunker
# ---------------------------------------------------------------------------

class TestTextChunker:
    def _chunk(self, content: str, max_chars: int = 5000):
        return list(TextChunker().chunk(content, max_chars))

    def test_chunk_single_paragraph_returns_one_chunk(self):
        content = "One paragraph of text."
        chunks = self._chunk(content)
        assert len(chunks) == 1
        assert chunks[0].text == "One paragraph of text."
        assert chunks[0].section == "(root)"

    def test_chunk_large_content_returns_multiple_chunks(self):
        content = "Para 1.\n\nPara 2.\n\nPara 3."
        chunks = self._chunk(content, max_chars=10)
        assert len(chunks) == 3
        assert chunks[0].section == "(root:1)"
        assert chunks[0].text == "Para 1."
        assert chunks[1].text == "Para 2."
        assert chunks[2].text == "Para 3."

    def test_chunk_small_content_returns_merged_chunk(self):
        content = "Short.\n\nAlso short."
        chunks = self._chunk(content, max_chars=1000)
        # Both paragraphs fit in one chunk
        assert len(chunks) == 1
        assert "Short." in chunks[0].text
        assert "Also short." in chunks[0].text

    def test_chunk_empty_content_returns_empty_list(self):
        chunks = self._chunk("")
        assert chunks == []

    def test_chunk_whitespace_content_returns_empty_list(self):
        chunks = self._chunk("   \n\n   ")
        assert chunks == []

    def test_chunk_content_returns_positive_start_line(self):
        content = "Para 1.\n\nPara 2."
        chunks = self._chunk(content, max_chars=10)
        for c in chunks:
            assert c.start_line >= 1
            assert c.end_line >= c.start_line


# ---------------------------------------------------------------------------
# ChunkerFactory
# ---------------------------------------------------------------------------

class TestChunkerFactory:
    def test_get_md_extension_returns_markdown_chunker(self):
        assert isinstance(ChunkerFactory.get(".md"), MarkdownChunker)

    def test_get_txt_extension_returns_text_chunker(self):
        assert isinstance(ChunkerFactory.get(".txt"), TextChunker)

    def test_get_json_extension_returns_text_chunker(self):
        assert isinstance(ChunkerFactory.get(".json"), TextChunker)

    def test_get_unknown_extension_returns_text_chunker(self):
        assert isinstance(ChunkerFactory.get(".xyz"), TextChunker)

    def test_get_uppercase_extension_returns_chunker_case_insensitive(self):
        """Extension matching must be case-insensitive."""
        assert isinstance(ChunkerFactory.get(".MD"), MarkdownChunker)
        assert isinstance(ChunkerFactory.get(".TXT"), TextChunker)
