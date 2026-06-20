import argparse
import os
from unittest.mock import patch

from cli.commands.skills_list import SkillsListCommand


def make_args(project="proj"):
    return argparse.Namespace(project=project)


def test_execute_no_skills_dir_prints_empty_message(tmp_path, capsys):
    with patch("cli.commands.skills_list.PROJECTS_ROOT", str(tmp_path)):
        cmd = SkillsListCommand()
        args = make_args()
        cmd.execute(args)
        captured = capsys.readouterr()
        assert "No skills installed in project" in captured.out


def test_execute_empty_skills_dir_prints_empty_message(tmp_path, capsys):
    with patch("cli.commands.skills_list.PROJECTS_ROOT", str(tmp_path)):
        skills_root = tmp_path / "proj" / "artifacts" / "skills"
        os.makedirs(skills_root, exist_ok=True)

        cmd = SkillsListCommand()
        args = make_args()
        cmd.execute(args)
        captured = capsys.readouterr()
        assert "No skills installed in project" in captured.out


def test_execute_lists_skill_folder_names(tmp_path, capsys):
    with patch("cli.commands.skills_list.PROJECTS_ROOT", str(tmp_path)):
        skills_root = tmp_path / "proj" / "artifacts" / "skills"
        os.makedirs(skills_root / "foo", exist_ok=True)
        os.makedirs(skills_root / "bar", exist_ok=True)

        cmd = SkillsListCommand()
        args = make_args()
        cmd.execute(args)
        captured = capsys.readouterr()
        assert "Installed skills in 'proj':" in captured.out
        assert "  - bar" in captured.out
        assert "  - foo" in captured.out


def test_execute_excludes_dot_prefixed_entries(tmp_path, capsys):
    with patch("cli.commands.skills_list.PROJECTS_ROOT", str(tmp_path)):
        skills_root = tmp_path / "proj" / "artifacts" / "skills"
        os.makedirs(skills_root / "foo", exist_ok=True)
        os.makedirs(skills_root / ".skills-registry.json", exist_ok=True)

        cmd = SkillsListCommand()
        args = make_args()
        cmd.execute(args)
        captured = capsys.readouterr()
        assert ".skills-registry.json" not in captured.out
        assert "  - foo" in captured.out


def test_execute_output_is_sorted_alphabetically(tmp_path, capsys):
    with patch("cli.commands.skills_list.PROJECTS_ROOT", str(tmp_path)):
        skills_root = tmp_path / "proj" / "artifacts" / "skills"
        os.makedirs(skills_root / "zebra", exist_ok=True)
        os.makedirs(skills_root / "apple", exist_ok=True)

        cmd = SkillsListCommand()
        args = make_args()
        cmd.execute(args)
        captured = capsys.readouterr()

        apple_idx = captured.out.index("apple")
        zebra_idx = captured.out.index("zebra")
        assert apple_idx < zebra_idx
