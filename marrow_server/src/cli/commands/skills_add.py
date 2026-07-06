import argparse
import os
import shutil

from config import PROJECTS_ROOT

from cli.commands.base import BaseCommand
from cli.services.github_fetcher import GitHubFetcher, GitHubFetchError, SkillNotFoundError
from cli.services.skills_registry import SkillsRegistry


class SkillsAddCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "skills-add"

    @property
    def help(self) -> str:
        return "Install a skill from a GitHub repository into a Marrow project"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "repo_url", help="GitHub repository URL (e.g. https://github.com/owner/repo)"
        )
        parser.add_argument("--project", required=True, help="Target project name")
        parser.add_argument(
            "--skill", required=True, help="Skill name (folder under skills/ in the repo)"
        )

    def execute(self, args: argparse.Namespace) -> None:
        skills_root = os.path.join(PROJECTS_ROOT, args.project, "artifacts", "skills")
        skill_dir = os.path.join(skills_root, args.skill)

        # REQ-07: abort if already exists
        if os.path.isdir(skill_dir):
            print(
                f"[ERROR] Skill '{args.skill}' already exists. "
                f"Use 'skills update --project {args.project} --skill {args.skill}' to refresh it."
            )
            raise SystemExit(1)

        # Risk-4: ensure skills_root exists
        os.makedirs(skills_root, exist_ok=True)

        # REQ-06: fetch from GitHub
        try:
            fetcher = GitHubFetcher(args.repo_url)
            fetcher.fetch_skill(args.skill, skill_dir)
        except SkillNotFoundError:
            print(f"[ERROR] Skill '{args.skill}' not found in repository '{args.repo_url}'.")
            if "private" in args.repo_url or True:  # always show hint
                print("       (If the repository is private, ensure it is public.)")  # Risk-5
            raise SystemExit(1)
        except GitHubFetchError as e:
            print(f"[ERROR] Failed to fetch skill: {e}")
            shutil.rmtree(skill_dir, ignore_errors=True)  # cleanup partial download
            raise SystemExit(1)
        except ValueError as e:
            print(f"[ERROR] Invalid repository URL: {e}")
            raise SystemExit(1)

        # REQ-15: write registry entry
        registry = SkillsRegistry(skills_root)
        registry.add(args.skill, args.repo_url)

        # REQ-06 / REQ-08: success output
        print(f"✓ Skill '{args.skill}' installed from {args.repo_url}.")
        print()
        print("→ Register it in role_profiles.yaml under the relevant role's playbooks[] list.")
