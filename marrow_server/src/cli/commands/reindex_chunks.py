import argparse
import logging
import os
from datetime import datetime

from tqdm import tqdm

from cli.commands.base import BaseCommand

logger = logging.getLogger("admin_cli")


class ReindexChunksCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "reindex-chunks"

    @property
    def help(self) -> str:
        return "Section-based chunk reindexing"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--project", required=True, help="Project name")
        parser.add_argument("--file", help="Only specifically named file (rel. path)")
        parser.add_argument("--dry-run", action="store_true", help="Do not save to database")

    def execute(self, args: argparse.Namespace) -> None:
        from config import PROJECTS_ROOT
        from storage import init_db
        from storage.repositories import ArtifactChunkRepository
        from tools.utils.cleaner import ContentCleaner

        project_root = os.path.abspath(os.path.join(PROJECTS_ROOT, args.project))
        if not os.path.exists(project_root):
            logger.error(f"Project not found: {args.project}")
            return

        init_db(project_root)

        repo = ArtifactChunkRepository(project_root)
        files_to_index = []

        if args.file:
            file_path = os.path.join(project_root, args.file)
            if os.path.exists(file_path):
                files_to_index.append(args.file)
            else:
                logger.error(f"File not found: {file_path}")
                return
        else:
            if not args.dry_run:
                try:
                    repo.table.delete("true")
                except Exception:
                    pass

            for root, dirs, files in os.walk(project_root):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for f in files:
                    if f.endswith((".md", ".txt", ".json")):
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
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, project_root).replace("\\", "/")
                        files_to_index.append(rel_path)

        if not files_to_index:
            logger.warning("No files for reindexing found.")
            return

        logger.info(f"Reindexing chunks for {len(files_to_index)} file(s)...")

        success_count = 0
        for rel_path in tqdm(files_to_index, desc="Chunks", unit="file"):
            try:
                full_path = os.path.join(project_root, rel_path)
                with open(full_path, encoding="utf-8") as f:
                    content = f.read()

                clean_content = ContentCleaner.clean(content)
                updated_at = datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()

                if not args.dry_run:
                    ext = os.path.splitext(rel_path)[1].lower()
                    repo.upsert_chunks(rel_path, clean_content, updated_at, ext=ext)

                success_count += 1

            except Exception as e:
                logger.error(f"Error reindexing chunks for {rel_path}: {e}")

        logger.info(f"Finished: {success_count} file(s) processed.")
