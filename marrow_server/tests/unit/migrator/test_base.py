from migrator.base import MigrationReport, MigrationStepReport


def test_migration_step_report_defaults_all_counts_zero_errors_empty():
    report = MigrationStepReport(subsystem="local_storage_layout", from_version=1, to_version=2)
    assert report.moved == 0
    assert report.skipped == 0
    assert report.collisions == 0
    assert report.errors == []


def test_migration_report_defaults_steps_and_errors_empty():
    report = MigrationReport(
        project="MyProject",
        subsystem="local_storage_layout",
        starting_version=1,
        ending_version=1,
    )
    assert report.steps == []
    assert report.errors == []
