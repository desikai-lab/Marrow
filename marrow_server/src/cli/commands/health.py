import argparse
import json
import os
import sys

from cli.commands.base import BaseCommand


class HealthCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "health"

    @property
    def help(self) -> str:
        return "Database integrity check"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--project", required=True, help="Project name")
        parser.add_argument("--json", action="store_true", help="Output as JSON")

    def execute(self, args: argparse.Namespace) -> None:
        from config import PROJECTS_ROOT
        from storage import check_integrity

        project_root = os.path.join(PROJECTS_ROOT, args.project)
        if not os.path.exists(project_root):
            print(f"Error: Project root not found: {project_root}")
            sys.exit(1)

        report = check_integrity(project_root)

        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return

        print(f"\n--- Database Integrity Report: {args.project} ---")
        print(f"Status: {report.get('status', 'error').upper()}")
        print(f"Total index records: {report.get('total_index_records', 0)}")

        if report.get("orphans_count", 0) > 0:
            print(
                f"\n[ERR] Orphans detected (DB entry exists, file missing): {report['orphans_count']}"
            )
        if report.get("dangling_blobs_count", 0) > 0:
            print(
                f"\n[WRN] Dangling blobs detected (File exists, DB entry missing): {report['dangling_blobs_count']}"
            )
        if report.get("inconsistencies_count", 0) > 0:
            print(f"\n[WRN] Metadata desync: {report['inconsistencies_count']}")

        if report.get("status") == "healthy":
            print("\n[OK] Database is consistent.")
        else:
            print("\n[!] Issues detected. Reindexing is recommended.")
