import argparse
import os
from unittest.mock import patch

import pytest

from cli.commands.skills_update import SkillsUpdateCommand
from cli.services.github_fetcher import GitHubFetchError, SkillNotFoundError


def make_args(project="proj", skill="my-skill"):
    return argparse.Namespace(project=project, skill=skill)


@patch("cli.commands.skills_update.SkillsRegistry")
def test_execute_skill_not_in_registry_exits_with_error(mock_registry_class, tmp_path, capsys):
    with patch("cli.commands.skills_update.PROJECTS_ROOT", str(tmp_path)):
        mock_registry = mock_registry_class.return_value
        mock_registry.get.return_value = None

        cmd = SkillsUpdateCommand()
        args = make_args()

        with pytest.raises(SystemExit) as excinfo:
            cmd.execute(args)

        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "not installed in project" in captured.out
        assert "skills add" in captured.out


@patch("cli.commands.skills_update.GitHubFetcher")
@patch("cli.commands.skills_update.SkillsRegistry")
def test_execute_deletes_existing_dir_before_fetch(
    mock_registry_class, mock_fetcher_class, tmp_path
):
    with patch("cli.commands.skills_update.PROJECTS_ROOT", str(tmp_path)):
        mock_registry = mock_registry_class.return_value
        mock_registry.get.return_value = {
            "name": "my-skill",
            "source_repo": "https://github.com/owner/repo",
        }

        cmd = SkillsUpdateCommand()
        args = make_args()

        with patch("cli.commands.skills_update.shutil.rmtree") as mock_rmtree:
            cmd.execute(args)
            skill_dir = os.path.join(str(tmp_path), "proj", "artifacts", "skills", "my-skill")
            mock_rmtree.assert_any_call(skill_dir, ignore_errors=True)


@patch("cli.commands.skills_update.GitHubFetcher")
@patch("cli.commands.skills_update.SkillsRegistry")
def test_execute_skill_not_found_in_remote_exits_with_error(
    mock_registry_class, mock_fetcher_class, tmp_path
):
    with patch("cli.commands.skills_update.PROJECTS_ROOT", str(tmp_path)):
        mock_registry = mock_registry_class.return_value
        mock_registry.get.return_value = {
            "name": "my-skill",
            "source_repo": "https://github.com/owner/repo",
        }
        mock_fetcher = mock_fetcher_class.return_value
        mock_fetcher.fetch_skill.side_effect = SkillNotFoundError()

        cmd = SkillsUpdateCommand()
        args = make_args()

        with pytest.raises(SystemExit) as excinfo:
            cmd.execute(args)

        assert excinfo.value.code == 1


@patch("cli.commands.skills_update.GitHubFetcher")
@patch("cli.commands.skills_update.SkillsRegistry")
def test_execute_github_fetch_error_exits_with_error(
    mock_registry_class, mock_fetcher_class, tmp_path
):
    with patch("cli.commands.skills_update.PROJECTS_ROOT", str(tmp_path)):
        mock_registry = mock_registry_class.return_value
        mock_registry.get.return_value = {
            "name": "my-skill",
            "source_repo": "https://github.com/owner/repo",
        }
        mock_fetcher = mock_fetcher_class.return_value
        mock_fetcher.fetch_skill.side_effect = GitHubFetchError("fetch failed")

        cmd = SkillsUpdateCommand()
        args = make_args()

        with pytest.raises(SystemExit) as excinfo:
            cmd.execute(args)

        assert excinfo.value.code == 1


@patch("cli.commands.skills_update.GitHubFetcher")
@patch("cli.commands.skills_update.SkillsRegistry")
def test_execute_success_updates_timestamp_and_prints(
    mock_registry_class, mock_fetcher_class, tmp_path, capsys
):
    with patch("cli.commands.skills_update.PROJECTS_ROOT", str(tmp_path)):
        mock_registry = mock_registry_class.return_value
        mock_registry.get.return_value = {
            "name": "my-skill",
            "source_repo": "https://github.com/owner/repo",
        }

        cmd = SkillsUpdateCommand()
        args = make_args()

        cmd.execute(args)

        mock_registry.update_timestamp.assert_called_once_with("my-skill")
        captured = capsys.readouterr()
        assert "✓ Skill 'my-skill' updated" in captured.out
