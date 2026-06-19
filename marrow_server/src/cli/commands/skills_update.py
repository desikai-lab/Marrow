import argparse
import os
import shutil

from config import PROJECTS_ROOT

from cli.commands.base import BaseCommand
from cli.services.github_fetcher import GitHubFetcher, GitHubFetchError, SkillNotFoundError
from cli.services.skills_registry import SkillsRegistry


class SkillsUpdateCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "skills-update"

    @property
    def help(self) -> str:
        return "Update an installed skill to the latest version from its source repository"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--project", required=True, help="Target project name")
        parser.add_argument("--skill", required=True, help="Skill name to update")

    def execute(self, args: argparse.Namespace) -> None:
        skills_root = os.path.join(PROJECTS_ROOT, args.project, "artifacts", "skills")
        skill_dir = os.path.join(skills_root, args.skill)
        registry = SkillsRegistry(skills_root)

        # REQ-13: must exist in registry to know source URL
        entry = registry.get(args.skill)
        if entry is None:
            print(
                f"[ERROR] Skill '{args.skill}' is not installed in project '{args.project}'. "
                f"Use 'skills add' to install it first."
            )
            raise SystemExit(1)

        source_repo = entry["source_repo"]

        # REQ-11: delete existing folder and re-fetch
        shutil.rmtree(skill_dir, ignore_errors=True)

        try:
            fetcher = GitHubFetcher(source_repo)
            fetcher.fetch_skill(args.skill, skill_dir)
        except SkillNotFoundError:
            print(f"[ERROR] Skill '{args.skill}' no longer found in repository '{source_repo}'.")
            raise SystemExit(1)
        except GitHubFetchError as e:
            print(f"[ERROR] Failed to fetch skill: {e}")
            shutil.rmtree(skill_dir, ignore_errors=True)
            raise SystemExit(1)

        # Update registry timestamp
        registry.update_timestamp(args.skill)

        print(f"✓ Skill '{args.skill}' updated from {source_repo}.")
