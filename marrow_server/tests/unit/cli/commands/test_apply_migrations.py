import argparse
from unittest.mock import MagicMock, patch

import pytest

from cli.commands.apply_migrations import ApplyMigrationsCommand


def make_args(project=None, dry_run=False):
    return argparse.Namespace(project=project, dry_run=dry_run)


def _fake_report(project="X", start=1, end=2, steps=None, errors=None):
    return MagicMock(project=project, starting_version=start, ending_version=end, steps=steps or [], errors=errors or [])


def test_execute_with_project_arg_calls_run_migrations_for_project_only():
    with (
        patch("cli.commands.apply_migrations.run_migrations_for_project", return_value=_fake_report()) as mock_single,
        patch("cli.commands.apply_migrations.run_migrations_all_projects") as mock_all,
    ):
        ApplyMigrationsCommand().execute(make_args(project="X"))

    mock_single.assert_called_once_with("X", dry_run=False)
    mock_all.assert_not_called()


def test_execute_no_project_arg_calls_run_migrations_all_projects():
    with (
        patch("cli.commands.apply_migrations.run_migrations_for_project") as mock_single,
        patch("cli.commands.apply_migrations.run_migrations_all_projects", return_value=[_fake_report()]) as mock_all,
    ):
        ApplyMigrationsCommand().execute(make_args(project=None))

    mock_all.assert_called_once_with(dry_run=False)
    mock_single.assert_not_called()


def test_execute_dry_run_flag_passes_dry_run_through_to_runner():
    with patch("cli.commands.apply_migrations.run_migrations_for_project", return_value=_fake_report()) as mock_single:
        ApplyMigrationsCommand().execute(make_args(project="X", dry_run=True))

    mock_single.assert_called_once_with("X", dry_run=True)


def test_execute_runner_raises_prints_error_and_exits_non_zero(capsys):
    with patch("cli.commands.apply_migrations.run_migrations_all_projects", side_effect=RuntimeError("boom")):
        with pytest.raises(SystemExit) as excinfo:
            ApplyMigrationsCommand().execute(make_args(project=None))

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "Critical Error" in captured.out


def test_name_and_help_return_expected_strings():
    cmd = ApplyMigrationsCommand()
    assert cmd.name == "apply-migrations"
    assert "migration" in cmd.help.lower()
