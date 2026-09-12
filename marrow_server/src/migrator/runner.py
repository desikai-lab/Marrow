import logging
import os

from common import path_resolver
from common.path_resolver import ResourceKind
from migrator import version_store
from migrator.base import MigrationReport
from migrator.migrations.local_storage_layout import REGISTRY as LOCAL_STORAGE_LAYOUT_REGISTRY

_logger = logging.getLogger("marrow.migrator")

_SUBSYSTEM = "local_storage_layout"


def run_migrations_for_project(project_name: str, dry_run: bool = False) -> MigrationReport:
    project_root = path_resolver.get_raw_path(project_name, "", ResourceKind.ROOT)
    meta = version_store.load_project_meta(project_name)
    current = version_store.get_subsystem_version(meta, _SUBSYSTEM)
    starting = current

    report = MigrationReport(project=project_name, subsystem=_SUBSYSTEM, starting_version=starting, ending_version=starting)

    pending = sorted((m for m in LOCAL_STORAGE_LAYOUT_REGISTRY if m.from_version >= current), key=lambda m: m.from_version)
    for migration in pending:
        if migration.from_version != current:
            # Non-contiguous registry (a gap) -- stop rather than skip a version silently.
            _logger.error("[migrator] %s: registry gap at version %d, stopping", project_name, current)
            report.errors.append({"subsystem": _SUBSYSTEM, "version": current, "error": "registry gap"})
            break
        try:
            step_report = migration.apply(project_root, dry_run=dry_run)
            report.steps.append(step_report)
            current = migration.to_version
            if not dry_run:
                meta.schema_versions[_SUBSYSTEM] = current
                version_store.save_project_meta(project_name, meta)  # persist after EACH step (ADR-0046 Decision 4, crash safety)
        except Exception as e:
            _logger.error("[migrator] %s: subsystem=%s from=%d to=%d failed: %s", project_name, _SUBSYSTEM, migration.from_version, migration.to_version, e)
            report.errors.append({"subsystem": _SUBSYSTEM, "from_version": migration.from_version, "to_version": migration.to_version, "error": str(e)})
            break  # version not bumped past this point -- other projects proceed independently (isolated by run_migrations_all_projects)

    report.ending_version = current
    return report


def run_migrations_all_projects(dry_run: bool = False) -> list[MigrationReport]:
    from config import PROJECTS_ROOT

    if not os.path.isdir(PROJECTS_ROOT):
        _logger.warning("[migrator] PROJECTS_ROOT not found, skipping migration pass.")
        return []

    reports: list[MigrationReport] = []
    project_names = [p for p in os.listdir(PROJECTS_ROOT) if os.path.isdir(os.path.join(PROJECTS_ROOT, p))]
    for project_name in project_names:
        try:
            reports.append(run_migrations_for_project(project_name, dry_run=dry_run))
        except Exception as e:
            _logger.error("[migrator] %s: unexpected top-level failure: %s", project_name, e)
            reports.append(MigrationReport(project=project_name, subsystem=_SUBSYSTEM, starting_version=-1, ending_version=-1, errors=[{"error": str(e)}]))
    return reports
