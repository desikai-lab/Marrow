import argparse
import os
import shutil

from cli.commands.base import BaseCommand

TEMPLATE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "project-template")
)


class InitCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "project-init"

    @property
    def help(self) -> str:
        return "Initialize a new project workspace from the built-in template"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--project", required=True, help="Project name (must be unique in TASKS_DIR)"
        )
        parser.add_argument(
            "--tasks-dir", default=None, help="Override TASKS_DIR environment variable"
        )

    def execute(self, args: argparse.Namespace) -> None:
        from config import PROJECTS_ROOT

        if args.tasks_dir:
            projects_root = os.path.join(os.path.abspath(args.tasks_dir), "projects")
        else:
            projects_root = PROJECTS_ROOT

        target = os.path.join(projects_root, args.project)

        if os.path.exists(target):
            print(f"[ERROR] Project '{args.project}' already exists at: {target}")
            raise SystemExit(1)

        template = os.path.abspath(TEMPLATE_DIR)
        if not os.path.isdir(template):
            print(f"[ERROR] Built-in template not found at: {template}")
            raise SystemExit(1)

        os.makedirs(projects_root, exist_ok=True)
        shutil.copytree(template, target)

        spec_path = os.path.join(target, "artifacts", "spec.md")
        fill_in_count = 0
        if os.path.isfile(spec_path):
            with open(spec_path, encoding="utf-8") as f:
                fill_in_count = f.read().count("FILL_IN")

        print(f"\n[Marrow] Project '{args.project}' initialized at: {target}")
        print()
        print("  ╔══════════════════════════════════════════════════════════════╗")
        print("  ║        NEXT STEPS — Complete your spec.md                    ║")
        print("  ╚══════════════════════════════════════════════════════════════╝")
        print()
        print(f"  spec.md contains {fill_in_count} {{{{FILL_IN}}}} markers that need your input.")
        print()
        print("  OPTION A — Fill manually:")
        print(f"    Open  : {spec_path}")
        print("    Search: FILL_IN")
        print("    Replace each marker with your project's actual values.")
        print()
        print("  OPTION B — Let an agent fill the gaps:")
        print("    Send this prompt to Claude (or any capable agent):")
        print()
        print("    ┌─────────────────────────────────────────────────────────┐")
        print("    │ I just initialized a new Marrow project called          │")
        print(f"    │ '{args.project}'. My stack is: [DESCRIBE YOUR STACK].  │")
        print("    │ Read my spec.md and replace every {{FILL_IN}} marker    │")
        print("    │ with the correct value for my project.                  │")
        print("    └─────────────────────────────────────────────────────────┘")
        print()
        print("  When spec.md is complete:")
        print("    Step 1: Start marrow_worker  →  point WATCH_ROOT at your src dir")
        print("    Step 2: Connect MCP client   →  see README.md#quickstart")
        print()
