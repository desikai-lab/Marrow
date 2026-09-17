import logging

import pytest

from tools.utils.project_settings import ProjectSettings, _parse_overlap_pct


class TestParseOverlapPct:
    def test_parse_overlap_pct_none_input_returns_none(self):
        assert _parse_overlap_pct(None) is None

    def test_parse_overlap_pct_empty_string_returns_none(self):
        assert _parse_overlap_pct("") is None
        assert _parse_overlap_pct("   ") is None

    def test_parse_overlap_pct_valid_value_returns_float(self):
        assert _parse_overlap_pct("0.2") == 0.2

    def test_parse_overlap_pct_zero_returns_zero(self):
        assert _parse_overlap_pct("0") == 0.0

    def test_parse_overlap_pct_non_numeric_returns_none_with_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = _parse_overlap_pct("not-a-number")
        assert result is None
        assert "Invalid CHUNK_OVERLAP_PCT" in caplog.text

    def test_parse_overlap_pct_negative_returns_none_with_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = _parse_overlap_pct("-0.1")
        assert result is None
        assert "out of range" in caplog.text

    def test_parse_overlap_pct_at_upper_bound_returns_none_with_warning(self, caplog):
        """Range is [0, 0.5) — 0.5 itself is out of range."""
        with caplog.at_level(logging.WARNING):
            result = _parse_overlap_pct("0.5")
        assert result is None
        assert "out of range" in caplog.text

    def test_parse_overlap_pct_just_under_upper_bound_returns_value(self):
        assert _parse_overlap_pct("0.49") == 0.49


class TestProjectSettingsChunkOverlapField:
    def test_project_settings_default_chunk_overlap_pct_is_none(self):
        assert ProjectSettings().chunk_overlap_pct is None
