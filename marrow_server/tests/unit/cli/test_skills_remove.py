import argparse
import os
from unittest.mock import patch

import pytest
from cli.commands.skills_remove import SkillsRemoveCommand
from cli.services.skills_registry import SkillNotRegisteredError


def make_args(project="proj", skill="my-skill"):
    return argparse.Namespace(project=project, skill=skill)


def test_execute_skill_not_installed_exits_with_error(tmp_path, capsys):
    with patch("cli.commands.skills_remove.PROJECTS_ROOT", str(tmp_path)):
        cmd = SkillsRemoveCommand()
        args = make_args()

        with pytest.raises(SystemExit) as excinfo:
            cmd.execute(args)

        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "not installed" in captured.out


def test_execute_removes_skill_directory(tmp_path):
    with patch("cli.commands.skills_remove.PROJECTS_ROOT", str(tmp_path)):
        skill_dir = tmp_path / "proj" / "artifacts" / "skills" / "my-skill"
        os.makedirs(skill_dir, exist_ok=True)

        cmd = SkillsRemoveCommand()
        args = make_args()

        with patch("cli.commands.skills_remove.SkillsRegistry"):
            cmd.execute(args)
            assert not os.path.exists(skill_dir)


@patch("cli.commands.skills_remove.SkillsRegistry")
def test_execute_removes_registry_entry(mock_registry_class, tmp_path):
    with patch("cli.commands.skills_remove.PROJECTS_ROOT", str(tmp_path)):
        skill_dir = tmp_path / "proj" / "artifacts" / "skills" / "my-skill"
        os.makedirs(skill_dir, exist_ok=True)

        mock_registry = mock_registry_class.return_value

        cmd = SkillsRemoveCommand()
        args = make_args()
        cmd.execute(args)

        mock_registry.remove.assert_called_once_with("my-skill")


@patch("cli.commands.skills_remove.SkillsRegistry")
def test_execute_tolerates_missing_registry_entry(mock_registry_class, tmp_path, capsys):
    with patch("cli.commands.skills_remove.PROJECTS_ROOT", str(tmp_path)):
        skill_dir = tmp_path / "proj" / "artifacts" / "skills" / "my-skill"
        os.makedirs(skill_dir, exist_ok=True)

        mock_registry = mock_registry_class.return_value
        mock_registry.remove.side_effect = SkillNotRegisteredError("not registered")

        cmd = SkillsRemoveCommand()
        args = make_args()

        # Should not raise SystemExit
        cmd.execute(args)

        captured = capsys.readouterr()
        assert "✓ Skill" in captured.out


@patch("cli.commands.skills_remove.SkillsRegistry")
def test_execute_prints_success_message(mock_registry_class, tmp_path, capsys):
    with patch("cli.commands.skills_remove.PROJECTS_ROOT", str(tmp_path)):
        skill_dir = tmp_path / "proj" / "artifacts" / "skills" / "my-skill"
        os.makedirs(skill_dir, exist_ok=True)

        cmd = SkillsRemoveCommand()
        args = make_args()
        cmd.execute(args)

        captured = capsys.readouterr()
        assert "✓ Skill 'my-skill' removed" in captured.out
