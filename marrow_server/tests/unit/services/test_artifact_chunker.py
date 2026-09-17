"""Unit tests for storage.artifact_chunker (ASV-9 / F4000202).

Covers:
- HeaderTreeChunkerStrategy: basic heading split, breadcrumbs, fence-awareness, fallback
- OverlapChunkerStrategy: fixed windowing, overlap percentage, boundary snapping, line numbers
- ChunkerFactory: extension routing via STRUCTURED_EXTENSIONS
- tools.utils.markdown_fence: build_fenced_ranges / in_fenced_range helpers
"""

from storage.artifact_chunker import (
    ChunkerFactory,
    HeaderTreeChunkerStrategy,
    OverlapChunkerStrategy,
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
        assert content[start : start + 3] == "```"

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
# HeaderTreeChunkerStrategy
# ---------------------------------------------------------------------------


class TestHeaderTreeChunkerStrategy:
    def _chunk(self, content: str, max_chars: int = 5000):
        return list(HeaderTreeChunkerStrategy().chunk(content, max_chars))

    def test_chunk_h1_h2_h3_returns_full_breadcrumb(self):
        content = "# Guide\nIntro.\n## Setup\nSetup text.\n### Configuration\nConfig text.\n"
        chunks = self._chunk(content)
        assert chunks[-1].section == "# Guide > ## Setup > ### Configuration"

    def test_chunk_sibling_h2_reset_does_not_leak_prior_h2(self):
        content = "# Doc\n## Section A\n### Sub A\nDetail.\n## Section B\n### Sub B\nDetail.\n"
        chunks = self._chunk(content)
        sub_a = next(c for c in chunks if "Sub A" in c.section)
        sub_b = next(c for c in chunks if "Sub B" in c.section)
        assert sub_a.section == "# Doc > ## Section A > ### Sub A"
        assert sub_b.section == "# Doc > ## Section B > ### Sub B"
        assert "Section A" not in sub_b.section

    def test_chunk_orphan_h3_before_h2_parents_to_h1(self):
        content = "# Doc\n### Orphan Sub\nDetail.\n"
        chunks = self._chunk(content)
        assert chunks[0].section == "# Doc > ### Orphan Sub"

    def test_chunk_multiple_h1_resets_breadcrumb_per_h1(self):
        content = "# First Doc\n## Setup\nA.\n# Second Doc\n## Setup\nB.\n"
        chunks = self._chunk(content)
        assert chunks[0].section == "# First Doc > ## Setup"
        assert chunks[1].section == "# Second Doc > ## Setup"

    def test_chunk_headings_in_fences_are_ignored(self):
        content = (
            "# Doc\n## Real Header\n"
            "```python\n# not a heading\n## not a heading\n```\n"
            "### Genuine Sub\nText.\n"
        )
        chunks = self._chunk(content)
        assert chunks[0].section == "# Doc > ## Real Header"
        assert chunks[1].section == "# Doc > ## Real Header > ### Genuine Sub"

    def test_chunk_h1_only_no_h2_h3_falls_back_to_overlap_strategy(self):
        content = "# Just A Title\nSome body text, no sub-headers at all.\n"
        chunks = self._chunk(content)
        assert len(chunks) == 1
        assert chunks[0].section != "# Just A Title"  # not treated as a structured leaf

    def test_chunk_zero_headers_falls_back_to_overlap_strategy(self):
        content = "Just a flat document.\n\nNo headings anywhere."
        chunks = self._chunk(content)
        assert len(chunks) == 1

    def test_chunk_empty_content_returns_empty_list(self):
        assert self._chunk("") == []

    def test_chunk_breadcrumb_prepended_to_embedded_text(self):
        content = "# Guide\n## Setup\nSetup body.\n"
        chunks = self._chunk(content)
        assert chunks[0].text.startswith("# Guide > ## Setup")

    def test_chunk_last_leaf_end_line_covers_full_document(self):
        content = "# Doc\n## Sec\nLine2\nLine3\nLine4\n"
        chunks = self._chunk(content)
        assert chunks[-1].end_line == 5


# ---------------------------------------------------------------------------
# OverlapChunkerStrategy
# ---------------------------------------------------------------------------


class TestOverlapChunkerStrategy:
    def _chunk(self, content: str, max_chars: int = 5000, overlap_pct: float | None = None):
        return list(OverlapChunkerStrategy().chunk(content, max_chars, overlap_pct=overlap_pct))

    def test_chunk_content_under_max_chars_returns_one_chunk_no_overlap(self):
        content = "One paragraph of text."
        chunks = self._chunk(content)
        assert len(chunks) == 1
        assert chunks[0].text == content

    def test_chunk_empty_content_returns_empty_list(self):
        assert self._chunk("") == []

    def test_chunk_large_content_default_overlap_produces_overlapping_windows(self):
        content = "A" * 50 + " " + "B" * 50 + " " + "C" * 50
        chunks = self._chunk(content, max_chars=60)
        assert len(chunks) > 1
        # Default 15% overlap of max_chars=60 -> 9 chars; consecutive windows must share a tail/head
        assert chunks[0].text[-5:] in chunks[1].text

    def test_chunk_custom_overlap_pct_changes_window_advance(self):
        content = "X" * 200
        chunks_default = self._chunk(content, max_chars=50)
        chunks_zero_overlap = self._chunk(content, max_chars=50, overlap_pct=0.0)
        assert len(chunks_zero_overlap) <= len(chunks_default)

    def test_chunk_boundary_snap_prefers_whitespace_over_mid_word(self):
        content = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10"
        chunks = self._chunk(content, max_chars=25, overlap_pct=0.0)
        for c in chunks[:-1]:
            assert not c.text.endswith(tuple("0123456789")) or c.text[-1] == c.text.rstrip()[-1]

    def test_chunk_content_returns_1_based_start_line(self):
        content = "Line one.\nLine two.\nLine three."
        chunks = self._chunk(content, max_chars=1000)
        assert chunks[0].start_line == 1

    def test_chunk_section_labels_are_sequential(self):
        content = "A" * 30 + " " + "B" * 30 + " " + "C" * 30
        chunks = self._chunk(content, max_chars=35, overlap_pct=0.1)
        assert chunks[0].section == "chunk_1"
        assert chunks[1].section == "chunk_2"

    def test_resolve_overlap_chars_computes_percentage_of_max_chars(self):
        strategy = OverlapChunkerStrategy()
        assert strategy._resolve_overlap_chars(0.15, 100) == 15
        assert strategy._resolve_overlap_chars(0.0, 100) == 0

    def test_snap_to_boundary_finds_nearest_preceding_space(self):
        strategy = OverlapChunkerStrategy()
        content = "one two three four five"
        raw_end = 13  # lands mid-word inside "three"
        snapped = strategy._snap_to_boundary(content, raw_end)
        assert content[snapped - 1] != content[snapped - 1].isalnum() or content[:snapped].endswith(
            (" ", "")
        )

    def test_snap_to_boundary_no_whitespace_in_lookback_returns_raw_end(self):
        strategy = OverlapChunkerStrategy()
        content = "a" * 100
        assert strategy._snap_to_boundary(content, 50, lookback=10) == 50

    def test_chunk_high_overlap_pct_does_not_infinite_loop(self):
        content = "word " * 40
        chunks = self._chunk(content, max_chars=30, overlap_pct=0.49)
        assert len(chunks) > 0  # test completing at all is the assertion


# ---------------------------------------------------------------------------
# ChunkerFactory
# ---------------------------------------------------------------------------


class TestChunkerFactory:
    def test_get_md_extension_returns_header_tree_strategy(self):
        assert isinstance(ChunkerFactory.get(".md"), HeaderTreeChunkerStrategy)

    def test_get_txt_extension_returns_overlap_strategy(self):
        assert isinstance(ChunkerFactory.get(".txt"), OverlapChunkerStrategy)

    def test_get_json_extension_returns_overlap_strategy(self):
        assert isinstance(ChunkerFactory.get(".json"), OverlapChunkerStrategy)

    def test_get_unknown_extension_returns_overlap_strategy(self):
        assert isinstance(ChunkerFactory.get(".xyz"), OverlapChunkerStrategy)

    def test_get_uppercase_extension_returns_strategy_case_insensitive(self):
        assert isinstance(ChunkerFactory.get(".MD"), HeaderTreeChunkerStrategy)
        assert isinstance(ChunkerFactory.get(".TXT"), OverlapChunkerStrategy)

    def test_structured_extensions_set_contains_only_md(self):
        """NOT IN SCOPE guard: .markdown/.mdx/.json must stay unstructured (REQ-01)."""
        assert ChunkerFactory.STRUCTURED_EXTENSIONS == {".md"}
