import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from storage.repositories.skeleton_repository import SkeletonRepository

logger = logging.getLogger("marrow.maintenance")


@dataclass
class MaintenanceReport:
    project_root: str
    versions_cleaned: bool = False
    files_compacted: bool = False
    ghosts_pruned: int = 0
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


class MaintenanceService:
    def __init__(
        self,
        project_root: str,
        project_name: str,
        skeleton_repo: SkeletonRepository,
        older_than_hours: int = 2,
    ):
        self.project_root = project_root
        self.project_name = project_name
        self.skeleton_repo = skeleton_repo
        self.older_than_hours = older_than_hours

    async def run(self) -> MaintenanceReport:
        """Execute all 3 phases independently."""
        t0 = time.monotonic()
        report = MaintenanceReport(project_root=self.project_root)

        report.versions_cleaned = await self._cleanup_versions(report.errors)
        report.files_compacted = await self._compact_files(report.errors)
        # report.ghosts_pruned = await self._prune_ghost_records(report.errors)

        report.duration_ms = (time.monotonic() - t0) * 1000
        logger.info(
            f"Maintenance completed for {self.project_name} in {report.duration_ms:.2f}ms. "
            f"Cleaned versions: {report.versions_cleaned}, Compacted: {report.files_compacted}, "
            # f"Ghosts pruned: {report.ghosts_pruned}. Errors: {len(report.errors)}"
        )
        return report

    async def _cleanup_versions(self, errors: list[str]) -> bool:
        try:
            await self.skeleton_repo.cleanup_old_versions(self.older_than_hours)
            return True
        except Exception as e:
            msg = f"Version cleanup failed: {e}"
            logger.error(msg)
            errors.append(msg)
            return False

    async def _compact_files(self, errors: list[str]) -> bool:
        try:
            await self.skeleton_repo.compact_files()
            return True
        except Exception as e:
            msg = f"File compaction failed: {e}"
            logger.error(msg)
            errors.append(msg)
            return False

    async def _prune_ghost_records(self, errors: list[str]) -> int:
        pruned_count = 0
        try:
            # Check row count first
            count = await asyncio.to_thread(self.skeleton_repo.table.count_rows)
            if count == 0:
                logger.info(f"Table is empty for {self.project_name}, skipping ghost pruning.")
                return pruned_count

            indexed_paths = await self.skeleton_repo.get_all_indexed_paths(
                self.project_name, include_tests=True
            )
            for path in indexed_paths:
                abs_path = Path(self.project_root) / path
                if not abs_path.exists():
                    # Check again to be safer (brief pause or re-stat)
                    if not abs_path.exists():
                        await self.skeleton_repo.delete_file_chunks(path, self.project_name)
                        pruned_count += 1
                        logger.debug(f"Pruned ghost record: {path}")
            return pruned_count
        except Exception as e:
            msg = f"Failed to prune ghost records: {e}"
            logger.error(msg)
            errors.append(msg)
            return pruned_count
