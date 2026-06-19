import argparse
import os

from cli.commands.base import BaseCommand
from config import PROJECTS_ROOT


class SkillsListCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "skills-list"

    @property
    def help(self) -> str:
        return "List all skills installed in a Marrow project"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--project", required=True, help="Target project name")

    def execute(self, args: argparse.Namespace) -> None:
        skills_root = os.path.join(PROJECTS_ROOT, args.project, "artifacts", "skills")

        # REQ-09: list skill subdirectories, exclude dot-prefixed entries
        if not os.path.isdir(skills_root):
            print(f"No skills installed in project '{args.project}'.")
            return

        skill_names = sorted(
            entry
            for entry in os.listdir(skills_root)
            if os.path.isdir(os.path.join(skills_root, entry)) and not entry.startswith(".")
        )

        # REQ-10: friendly empty-state message
        if not skill_names:
            print(f"No skills installed in project '{args.project}'.")
            return

        print(f"Installed skills in '{args.project}':")
        for name in skill_names:
            print(f"  - {name}")
