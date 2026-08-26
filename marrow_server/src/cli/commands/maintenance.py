import argparse
import asyncio
import os
import sys

from cli.commands.base import BaseCommand


class MaintenanceCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "maintenance"

    @property
    def help(self) -> str:
        return "LanceDB Maintenance: compaction, version cleanup, and ghost pruning"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--project", help="Run maintenance for a single named project")
        group.add_argument(
            "--all-projects", action="store_true", help="Discover and run for all projects"
        )
        parser.add_argument(
            "--older-than-hours", type=int, default=2, help="Version cleanup window (default: 2)"
        )
        parser.add_argument("--dry-run", action="store_true", help="No-op log only execution")

    def execute(self, args: argparse.Namespace) -> None:
        from config import PROJECTS_ROOT
        from services.maintenance_service import MaintenanceService
        from storage.ghost_pruner import FilesystemExistenceStrategy, GhostPruner
        from storage.repositories.artifact_repository import ArtifactChunkRepository
        from storage.repositories.skeleton_repository import SkeletonRepository

        async def run_for_project(project_name: str):
            project_root = os.path.join(PROJECTS_ROOT, project_name)
            db_path = os.path.join(project_root, ".db", "index.lancedb")

            if not os.path.exists(db_path):
                print(f"Skipping {project_name}: DB path not found at {db_path}")
                return

            print(f"Starting maintenance for project: {project_name}")
            if args.dry_run:
                print(f"[DRY-RUN] Would run maintenance on {project_name}")
                return

            try:
                skeleton_repo = SkeletonRepository(project_root)
                artifact_chunk_repo = ArtifactChunkRepository(project_root)
                artifact_strategy = FilesystemExistenceStrategy(
                    root_resolver=lambda project: os.path.join(PROJECTS_ROOT, project, "artifacts")
                )

                artifact_pruner = GhostPruner(repo=artifact_chunk_repo, strategy=artifact_strategy)

                service = MaintenanceService(
                    project_root=project_root,
                    project_name=project_name,
                    skeleton_repo=skeleton_repo,
                    older_than_hours=args.older_than_hours,
                    artifact_ghost_pruner=artifact_pruner,
                )

                report = await service.run()
                if report.errors:
                    print(f"Completed with errors for {project_name}: {report.errors}")
                else:
                    print(
                        f"Maintenance finished successfully for {project_name}. "
                        f"Compact: {report.files_compacted}, "
                        f"Cleanup: {report.versions_cleaned}, "
                        f"Ghosts Pruned: {report.ghosts_pruned}, "
                        f"Artifact Chunks Pruned: {report.artifact_chunks_pruned}"
                    )

            except Exception as e:
                print(f"Failed to run maintenance for {project_name}: {e}")

        async def main_maintenance():
            if args.project:
                await run_for_project(args.project)
            elif args.all_projects:
                if not os.path.exists(PROJECTS_ROOT):
                    print(f"Error: Projects root not found: {PROJECTS_ROOT}")
                    sys.exit(1)

                for project_name in os.listdir(PROJECTS_ROOT):
                    if os.path.isdir(os.path.join(PROJECTS_ROOT, project_name)):
                        await run_for_project(project_name)

        asyncio.run(main_maintenance())
