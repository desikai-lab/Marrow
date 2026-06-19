import argparse
import os
import shutil

from config import PROJECTS_ROOT

from cli.commands.base import BaseCommand
from cli.services.skills_registry import SkillNotRegisteredError, SkillsRegistry


class SkillsRemoveCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "skills-remove"

    @property
    def help(self) -> str:
        return "Remove an installed skill from a Marrow project"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--project", required=True, help="Target project name")
        parser.add_argument("--skill", required=True, help="Skill name to remove")

    def execute(self, args: argparse.Namespace) -> None:
        skills_root = os.path.join(PROJECTS_ROOT, args.project, "artifacts", "skills")
        skill_dir = os.path.join(skills_root, args.skill)

        # REQ-14b: abort if skill folder does not exist
        if not os.path.isdir(skill_dir):
            print(f"[ERROR] Skill '{args.skill}' is not installed in project '{args.project}'.")
            raise SystemExit(1)

        # REQ-14: delete folder
        shutil.rmtree(skill_dir)

        # Clean up registry entry (best-effort: do not crash if entry absent)
        registry = SkillsRegistry(skills_root)
        try:
            registry.remove(args.skill)
        except SkillNotRegisteredError:
            pass  # skill was manually installed without registry; still removed from disk

        print(f"✓ Skill '{args.skill}' removed from project '{args.project}'.")
