import argparse
import sys

from migrator.runner import run_migrations_all_projects, run_migrations_for_project

from cli.commands.base import BaseCommand


class ApplyMigrationsCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "apply-migrations"

    @property
    def help(self) -> str:
        return "Run pending schema migrations for one project or all projects."

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--project", required=False, help="Project name (omit to run for all projects)"
        )
        parser.add_argument("--dry-run", action="store_true", help="Only show planned changes")

    def execute(self, args: argparse.Namespace) -> None:
        try:
            if args.project:
                reports = [run_migrations_for_project(args.project, dry_run=args.dry_run)]
            else:
                reports = run_migrations_all_projects(dry_run=args.dry_run)

            for report in reports:
                print(
                    f"\n--- {report.project}: {report.starting_version} -> {report.ending_version} ---"
                )
                for step in report.steps:
                    print(
                        f"  step {step.from_version}->{step.to_version}: moved={step.moved} collisions={step.collisions} errors={len(step.errors)}"
                    )
                if report.errors:
                    print(f"  project-level errors: {report.errors}")

            if args.dry_run:
                print("\n[INFO] Dry run finished. No changes were persisted.")
            else:
                print("\n[SUCCESS] Migration pass completed.")
        except Exception as e:
            print(f"Critical Error: {e}")
            sys.exit(1)
