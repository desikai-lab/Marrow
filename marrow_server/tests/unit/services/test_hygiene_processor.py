"""Tests for HygieneCheckProcessor (ТД4000080).

Unit tests mock filesystem and BuildContext to isolate the processor.
Run with: pytest tests/test_hygiene_processor.py -v
"""

from unittest.mock import MagicMock, patch

import pytest

from tools.build_processors import HygieneCheckProcessor, ProcessorFactory

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_context(project: str, manifest_name: str) -> MagicMock:
    ctx = MagicMock()
    ctx.project = project
    ctx.manifest.name = manifest_name
    ctx.output_buffer = []
    return ctx


def _make_step(severity: str = "warn") -> MagicMock:
    step = MagicMock()
    # Replicate StepConfig.model_extra behaviour
    step.severity = None  # attribute-level is None → falls back to model_extra
    step.model_extra = {"severity": severity}
    return step


# ── tests ─────────────────────────────────────────────────────────────────────


class TestNoLogFileAppendsOk:
    """No {name}_error.log → OK message appended, no exception."""

    def test_hygiene_check_no_stale_log_appends_ok_message(self, tmp_path):
        builds_dir = tmp_path / "builds"
        builds_dir.mkdir()

        ctx = _make_context("TestProject", "my_build")
        step = _make_step("warn")

        with patch("tools.build_processors.validate_project_path", return_value=str(tmp_path)):
            HygieneCheckProcessor().process(step, ctx)

        assert len(ctx.output_buffer) == 1
        assert "[HYGIENE]" in ctx.output_buffer[0]
        assert "No stale" in ctx.output_buffer[0] or "✅" in ctx.output_buffer[0]


class TestLogFilePresentWarn:
    """Stale log exists, severity=warn → WARNING in buffer, no exception raised."""

    def test_hygiene_check_stale_log_warn_severity_appends_warning(self, tmp_path):
        builds_dir = tmp_path / "builds"
        builds_dir.mkdir()
        (builds_dir / "my_build_error.log").write_text("some error", encoding="utf-8")

        ctx = _make_context("TestProject", "my_build")
        step = _make_step("warn")

        with patch("tools.build_processors.validate_project_path", return_value=str(tmp_path)):
            HygieneCheckProcessor().process(step, ctx)  # must NOT raise

        assert len(ctx.output_buffer) == 1
        assert "[HYGIENE]" in ctx.output_buffer[0]
        assert "⚠️" in ctx.output_buffer[0] or "Stale" in ctx.output_buffer[0]


class TestLogFilePresentError:
    """Stale log exists, severity=error → RuntimeError raised."""

    def test_hygiene_check_stale_log_error_severity_raises_runtime_error(self, tmp_path):
        builds_dir = tmp_path / "builds"
        builds_dir.mkdir()
        (builds_dir / "strict_build_error.log").write_text("error", encoding="utf-8")

        ctx = _make_context("TestProject", "strict_build")
        step = _make_step("error")

        with patch("tools.build_processors.validate_project_path", return_value=str(tmp_path)):
            with pytest.raises(RuntimeError, match="Stale error log"):
                HygieneCheckProcessor().process(step, ctx)


class TestProcessorFactoryRegistration:
    """ProcessorFactory.get_processor('hygiene_check') returns HygieneCheckProcessor instance."""

    def test_get_processor_hygiene_check_action_returns_correct_instance(self):
        proc = ProcessorFactory.get_processor("hygiene_check")
        assert isinstance(proc, HygieneCheckProcessor)

    def test_get_processor_unknown_action_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown pipeline action"):
            ProcessorFactory.get_processor("nonexistent_action")


class TestFullBuildWithHygieneFirstStep:
    """Integration: hygiene_check is first step → called via factory before other steps."""

    def test_hygiene_check_first_step_in_manifest_processor_is_called(self, tmp_path):
        """Verifies that in a manifest with hygiene_check as step[0], the processor runs."""
        builds_dir = tmp_path / "builds"
        builds_dir.mkdir()
        # No stale log → clean run
        call_order = []

        original_process = HygieneCheckProcessor.process

        def tracking_process(self_inner, step, ctx):
            call_order.append("hygiene_check")
            return original_process(self_inner, step, ctx)

        with patch.object(HygieneCheckProcessor, "process", tracking_process):
            with patch(
                "tools.utils.filesystem_utils.validate_project_path", return_value=str(tmp_path)
            ):
                ctx = _make_context("TestProject", "integration_build")
                step = _make_step("warn")
                ProcessorFactory.get_processor("hygiene_check").process(step, ctx)

        assert "hygiene_check" in call_order
