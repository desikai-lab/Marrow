import argparse
import os
from unittest.mock import patch

import pytest

from cli.commands.skills_add import SkillsAddCommand
from cli.services.github_fetcher import GitHubFetchError, SkillNotFoundError


def make_args(project="proj", skill="my-skill", repo_url="https://github.com/owner/repo"):
    return argparse.Namespace(project=project, skill=skill, repo_url=repo_url)


def test_execute_skill_already_exists_prints_error_and_exits(tmp_path):
    with patch("cli.commands.skills_add.PROJECTS_ROOT", str(tmp_path)):
        skill_dir = tmp_path / "proj" / "artifacts" / "skills" / "my-skill"
        os.makedirs(skill_dir, exist_ok=True)

        cmd = SkillsAddCommand()
        args = make_args()

        with pytest.raises(SystemExit) as excinfo:
            cmd.execute(args)

        assert excinfo.value.code == 1


@patch("cli.commands.skills_add.GitHubFetcher")
def test_execute_skill_not_found_in_repo_exits_with_error(mock_fetcher_class, tmp_path):
    with patch("cli.commands.skills_add.PROJECTS_ROOT", str(tmp_path)):
        mock_fetcher = mock_fetcher_class.return_value
        mock_fetcher.fetch_skill.side_effect = SkillNotFoundError()

        cmd = SkillsAddCommand()
        args = make_args()

        with pytest.raises(SystemExit) as excinfo:
            cmd.execute(args)

        assert excinfo.value.code == 1


@patch("cli.commands.skills_add.GitHubFetcher")
def test_execute_github_fetch_error_cleans_up_and_exits(mock_fetcher_class, tmp_path):
    with patch("cli.commands.skills_add.PROJECTS_ROOT", str(tmp_path)):
        mock_fetcher = mock_fetcher_class.return_value
        mock_fetcher.fetch_skill.side_effect = GitHubFetchError("fetch failed")

        cmd = SkillsAddCommand()
        args = make_args()

        with patch("cli.commands.skills_add.shutil.rmtree") as mock_rmtree:
            with pytest.raises(SystemExit) as excinfo:
                cmd.execute(args)

            assert excinfo.value.code == 1
            skill_dir = os.path.join(str(tmp_path), "proj", "artifacts", "skills", "my-skill")
            mock_rmtree.assert_called_once_with(skill_dir, ignore_errors=True)


@patch("cli.commands.skills_add.GitHubFetcher")
def test_execute_invalid_repo_url_exits_with_error(mock_fetcher_class, tmp_path):
    with patch("cli.commands.skills_add.PROJECTS_ROOT", str(tmp_path)):
        mock_fetcher_class.side_effect = ValueError("Invalid URL")

        cmd = SkillsAddCommand()
        args = make_args()

        with pytest.raises(SystemExit) as excinfo:
            cmd.execute(args)

        assert excinfo.value.code == 1


@patch("cli.commands.skills_add.SkillsRegistry")
@patch("cli.commands.skills_add.GitHubFetcher")
def test_execute_success_writes_registry_and_prints_reminder(
    mock_fetcher_class, mock_registry_class, tmp_path, capsys
):
    with patch("cli.commands.skills_add.PROJECTS_ROOT", str(tmp_path)):
        mock_registry = mock_registry_class.return_value

        cmd = SkillsAddCommand()
        args = make_args()

        cmd.execute(args)

        mock_fetcher_class.return_value.fetch_skill.assert_called_once()
        mock_registry.add.assert_called_once_with("my-skill", "https://github.com/owner/repo")

        captured = capsys.readouterr()
        assert "✓ Skill" in captured.out
        assert "role_profiles.yaml" in captured.out


@patch("cli.commands.skills_add.SkillsRegistry")
@patch("cli.commands.skills_add.GitHubFetcher")
def test_execute_creates_skills_root_if_missing(mock_fetcher_class, mock_registry_class, tmp_path):
    with patch("cli.commands.skills_add.PROJECTS_ROOT", str(tmp_path)):
        skills_root = tmp_path / "proj" / "artifacts" / "skills"
        assert not skills_root.exists()

        cmd = SkillsAddCommand()
        args = make_args()

        cmd.execute(args)

        assert skills_root.exists()
