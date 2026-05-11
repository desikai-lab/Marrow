import sys
import argparse
from cli.commands.base import BaseCommand

class MigrateCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "migrate"
        
    @property
    def help(self) -> str:
        return "Migrate YAML tasks to LanceDB"
        
    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--project", required=True, help="Project name")
        parser.add_argument("--dry-run", action="store_true", help="Only show planned changes")
        parser.add_argument("--force", action="store_true", help="Force update existing records")
        
    def execute(self, args: argparse.Namespace) -> None:
        from storage.migrate import sync_initial
        
        print(f"\n--- Starting Migration: Project '{args.project}' ---")
        if args.dry_run:
            print("[DRY_RUN] No changes will be persisted.")
            
        try:
            report = sync_initial(args.project, dry_run=args.dry_run, force=args.force)
            print(f"Tasks created/updated: {report.created}")
            print(f"Skipped: {report.skipped}")
            
            if report.errors:
                print(f"\nErrors encountered: {len(report.errors)}")
                for i, err in enumerate(report.errors[:10]):
                    print(f"  {i+1}. {err}")
                if len(report.errors) > 10:
                    print(f"  ... and {len(report.errors) - 10} more errors.")
                    
            if report.created > 0 and not args.dry_run:
                print("\n[SUCCESS] Migration completed successfully.")
            elif args.dry_run:
                print("\n[INFO] Dry run finished.")
        except Exception as e:
            print(f"Critical Error: {e}")
            sys.exit(1)
