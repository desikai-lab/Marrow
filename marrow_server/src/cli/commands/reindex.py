import argparse
import logging
import os
from datetime import datetime
from pathlib import Path

from tqdm import tqdm

from cli.commands.base import BaseCommand

logger = logging.getLogger("admin_cli")


class ReindexCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "reindex"

    @property
    def help(self) -> str:
        return "Vector reindexing"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--project", required=True, help="Project name")
        parser.add_argument(
            "--target",
            choices=["tasks", "artifacts", "both"],
            default="both",
            help="Reindexing target",
        )
        parser.add_argument("--dry-run", action="store_true", help="Do not save to database")

    def execute(self, args: argparse.Namespace) -> None:
        from config import PROJECTS_ROOT
        from storage import init_db

        project_root = os.path.abspath(os.path.join(PROJECTS_ROOT, args.project))
        if not os.path.exists(project_root):
            logger.error(f"Project not found: {args.project}")
            return

        # Ensure DB structure exists
        init_db(project_root)

        if args.target in ["tasks", "both"]:
            self._reindex_tasks(args.project, project_root, args.dry_run)

        if args.target in ["artifacts", "both"]:
            self._reindex_artifacts(args.project, project_root, args.dry_run)

    def _reindex_tasks(self, project_name: str, project_root: str, dry_run: bool):
        from storage import upsert_task
        from storage.migrate import load_task_from_blob

        blobs_path = os.path.join(project_root, ".db", "blobs")
        if not os.path.exists(blobs_path):
            logger.error(f"Blobs folder not found: {blobs_path}")
            return

        all_blobs = list(Path(blobs_path).rglob("*.md"))
        if not all_blobs:
            logger.warning(f"No tasks found for project {project_name}.")
            return

        logger.info(f"Reindexing {len(all_blobs)} tasks for project '{project_name}'...")

        success_count = 0
        for blob_path in tqdm(all_blobs, desc="Tasks", unit="task"):
            try:
                task = load_task_from_blob(str(blob_path), project_name)
                if task:
                    # Update relative path
                    rel_path = os.path.relpath(blob_path, project_root).replace("\\", "/")
                    task.file_path = rel_path
                    if not dry_run:
                        upsert_task(project_root, task)
                    success_count += 1
            except Exception as e:
                logger.error(f"Error indexing {blob_path.name}: {e}")

        logger.info(f"Finished: {success_count} tasks reindexed.")

    def _reindex_artifacts(self, project_name: str, project_root: str, dry_run: bool):
        from storage import ArtifactRecord, get_artifact_table
        from storage.embeddings import embeddings_manager
        from tools.utils.cleaner import ContentCleaner

        logger.info(f"Reindexing artifacts for project '{project_name}'...")

        all_files = []
        for root_dir, dirs, files in os.walk(project_root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if f.endswith(".md"):
                    if any(
                        x in f.lower()
                        for x in [
                            "backlog_active",
                            "backlog_paused",
                            "backlog_done",
                            "backlog_index",
                        ]
                    ):
                        continue
                    all_files.append(os.path.join(root_dir, f))

        if not all_files:
            logger.warning(f"No artifacts (.md files) found for project {project_name}.")
            return

        table = get_artifact_table(project_root)
        if not dry_run:
            try:
                table.delete("true")
            except Exception:
                pass

        success_count = 0
        records = []

        for file_path in tqdm(all_files, desc="Artifacts", unit="file"):
            try:
                rel_path = os.path.relpath(file_path, project_root).replace("\\", "/")
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                clean_content = ContentCleaner.clean(content)

                if not dry_run:
                    from config import EMBEDDING_MODEL_TEXT

                    vector = embeddings_manager.generate_vector(
                        clean_content, model_name=EMBEDDING_MODEL_TEXT
                    )

                updated = datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()

                record = ArtifactRecord(path=rel_path, updated=updated, vector=vector)

                if not dry_run:
                    records.append(record.to_index_row())
                success_count += 1

            except Exception as e:
                logger.error(f"Error indexing {file_path}: {e}")

        if records and not dry_run:
            table.add(records)

        logger.info(f"Finished: {success_count} artifacts reindexed.")
