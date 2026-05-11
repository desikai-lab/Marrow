import argparse
import logging
import os

from cli.commands.base import BaseCommand

logger = logging.getLogger("diag_index")


class DiagIndexCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "diag-index"

    @property
    def help(self) -> str:
        return "Diagnose the code skeleton index for a project"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--project", required=True,
            help="Project name to inspect (e.g. 'marrow_server')"
        )

    def execute(self, args: argparse.Namespace) -> None:
        from config import PROJECTS_ROOT
        from storage.db import get_skeleton_table

        project = args.project
        project_root = os.path.join(PROJECTS_ROOT, project)

        logger.info("Opening skeleton index for project '%s' at: %s", project, project_root)
        try:
            table = get_skeleton_table(project_root)
        except Exception as e:
            print(f"[ERROR] Could not open skeleton index: {e}")
            raise SystemExit(1)

        total = table.count_rows()
        logger.info("Index opened. Total rows: %d", total)

        sample       = table.search().limit(5).to_list()
        file_rows    = table.search().where("chunk_type = 'file'").to_list()
        test_rows    = table.search().where("is_test = true").limit(10000).to_list()
        notest_rows  = table.search().where("is_test = false").limit(10000).to_list()
        proj_rows    = table.search().where(f"project = '{project}'").limit(10000).to_list()
        full_query   = table.search().where(
            f"project = '{project}' AND chunk_type = 'file' AND is_test = false"
        ).to_list()
        no_filter    = table.search().where(
            f"project = '{project}' AND chunk_type = 'file'"
        ).to_list()

        print(f"\n[Marrow] diag-index — project: '{project}'")
        print(f"  Total rows                                  : {total}")
        print(f"  chunk_type='file'                           : {len(file_rows)}")
        print(f"  is_test=true                                : {len(test_rows)}")
        print(f"  is_test=false                               : {len(notest_rows)}")
        print(f"  project='{project}'                        : {len(proj_rows)}")
        print(f"  project + file + is_test=false (full query) : {len(full_query)}")
        print(f"  project + file (no is_test filter)          : {len(no_filter)}")

        if sample:
            print(f"\n  Sample row keys : {list(sample[0].keys())}")
            print("  Sample rows:")
            for row in sample:
                print(
                    f"    project={row.get('project')!r}  "
                    f"chunk_type={row.get('chunk_type')!r}  "
                    f"is_test={row.get('is_test')!r}  "
                    f"path={row.get('path')!r}"
                )

        if no_filter:
            print("\n  Sample (project + file, no is_test filter):")
            for r in no_filter[:3]:
                print(f"    path={r.get('path')!r}  is_test={r.get('is_test')!r}")
        print()
