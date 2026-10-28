from unittest.mock import MagicMock, patch

from cli.commands.apply_migrations import ApplyMigrationsCommand


def make_args(project=None, dry_run=False):
    class Args:
        def __init__(self):
            self.project = project
            self.dry_run = dry_run

    return Args()


def _fake_report(start=2, end=3, steps=None):
    class Report:
        def __init__(self):
            self.project = "X"
            self.starting_version = start
            self.ending_version = end
            self.steps = steps or []
            self.errors = []

    return Report()


def test_execute_step_with_skipped_and_error_prints_skipped_and_error_detail(capsys):
    step = MagicMock(from_version=2, to_version=3, moved=1, skipped=2, collisions=0)
    step.errors = [{'file': 'role_profiles.yaml', 'error': 'manual step: add the init role'}]
    report = _fake_report(start=2, end=3, steps=[step])

    with patch(
        'cli.commands.apply_migrations.run_migrations_for_project', return_value=report
    ):
        ApplyMigrationsCommand().execute(make_args(project='X'))

    out = capsys.readouterr().out
    assert 'skipped=2' in out
    assert 'manual step: add the init role' in out
