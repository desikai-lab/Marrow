import os
import re
import shutil

from common import path_resolver
from common.path_resolver import NAMESPACE_ARTIFACTS, NAMESPACE_TASKS, ResourceKind
from migrator.base import Migration, MigrationStepReport

# Matches path_resolver.HISTORY_TIMESTAMP_FORMAT ("%Y%m%d_%H%M%S") appended as a filename suffix.
_OLD_SCHEME_RE = re.compile(r"^(.+)_(\d{8}_\d{6})(\.\w+)$")


class V1ToV2HistoryFolderScheme(Migration):
    subsystem = "local_storage_layout"
    from_version = 1
    to_version = 2

    def apply(self, project_root: str, dry_run: bool = False) -> MigrationStepReport:
        report = MigrationStepReport(subsystem=self.subsystem, from_version=self.from_version, to_version=self.to_version)
        for namespace in (NAMESPACE_ARTIFACTS, NAMESPACE_TASKS):
            self._migrate_namespace(project_root, namespace, dry_run, report)
        return report

    def _migrate_namespace(self, project_root: str, namespace: str, dry_run: bool, report: MigrationStepReport) -> None:
        namespace_root = path_resolver.get_raw_path(project_root, namespace, ResourceKind.HISTORY)
        if not os.path.isdir(namespace_root):
            return

        for dirpath, _dirnames, filenames in os.walk(namespace_root):
            for fname in filenames:
                match = _OLD_SCHEME_RE.match(fname)
                if not match:
                    continue
                self._migrate_one_file(dirpath, fname, match, dry_run, report)

    def _migrate_one_file(self, dirpath: str, fname: str, match: re.Match, dry_run: bool, report: MigrationStepReport) -> None:
        name, timestamp, ext = match.groups()
        src = os.path.join(dirpath, fname)
        dest_dir = os.path.join(dirpath, f"{name}{ext}")
        dest = os.path.join(dest_dir, f"{timestamp}{ext}")

        try:
            if os.path.exists(dest):
                dest = self._disambiguate(dest_dir, timestamp, ext)
                report.collisions += 1
            if dry_run:
                report.moved += 1
                return
            os.makedirs(dest_dir, exist_ok=True)
            self._move(src, dest)
            report.moved += 1
        except Exception as e:
            report.errors.append({"file": src, "error": str(e)})

    @staticmethod
    def _disambiguate(dest_dir: str, timestamp: str, ext: str) -> str:
        candidate = os.path.join(dest_dir, f"{timestamp}_migrated{ext}")
        n = 2
        while os.path.exists(candidate):
            candidate = os.path.join(dest_dir, f"{timestamp}_migrated{n}{ext}")
            n += 1
        return candidate

    @staticmethod
    def _move(src: str, dest: str) -> None:
        """rename-with-copy-fallback: os.rename is not guaranteed atomic across filesystem/volume
        boundaries (architecture.md §7 risk). Never copy-and-leave-the-original (REQ-01)."""
        try:
            os.rename(src, dest)
        except OSError:
            shutil.copy2(src, dest)
            if os.path.getsize(src) != os.path.getsize(dest):
                os.remove(dest)
                raise
            os.remove(src)
