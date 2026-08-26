import argparse
import asyncio
import logging
import os
from datetime import datetime, timedelta

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

        artifacts_root = os.path.join(project_root, "artifacts")
        search_root = artifacts_root if os.path.exists(artifacts_root) else project_root

        if args.file:
            target_path = args.file.replace("\\", "/")
            file_path = os.path.join(search_root, target_path)
            if os.path.exists(file_path):
                files_to_index.append(target_path)
            else:
                logger.error(f"File not found: {file_path}")
                return
        else:
            if not args.dry_run:
                try:
                    repo.table.delete("true")
                except Exception:
                    pass

            for root, dirs, files in os.walk(search_root):
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
                        rel_path = os.path.relpath(full_path, search_root).replace("\\", "/")
                        files_to_index.append(rel_path)

        if not files_to_index:
            logger.warning("No files for reindexing found.")
            return

        logger.info(f"Reindexing chunks for {len(files_to_index)} file(s)...")

        async def _run_reindex() -> int:
            count = 0
            for rel_path in tqdm(files_to_index, desc="Chunks", unit="file"):
                try:
                    full_path = os.path.join(search_root, rel_path)
                    with open(full_path, encoding="utf-8") as f:
                        content = f.read()

                    clean_content = ContentCleaner.clean(content)
                    updated_at = datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()

                    if not args.dry_run:
                        ext = os.path.splitext(rel_path)[1].lower()
                        await repo.upsert_chunks(rel_path, clean_content, updated_at, ext=ext)

                    count += 1

                except Exception as e:
                    logger.error(f"Error reindexing chunks for {rel_path}: {e}")

            return count

        success_count = asyncio.run(_run_reindex())
        logger.info(f"Finished: {success_count} file(s) processed.")

        if not args.dry_run:
            # Bulk upserts accumulate many small fragments and version manifests.
            # Compact and purge immediately so disk usage stays bounded.
            try:
                repo.table.compact_files()
                logger.info("artifact_chunks: compacted files.")
            except Exception as e:
                logger.warning(f"Post-reindex compact_files failed: {e}")
            try:
                repo.table.cleanup_old_versions(
                    older_than=timedelta(minutes=0), delete_unverified=True
                )
                logger.info("artifact_chunks: purged old version snapshots.")
            except Exception as e:
                logger.warning(f"Post-reindex cleanup_old_versions failed: {e}")
