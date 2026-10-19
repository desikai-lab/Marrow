from pathlib import Path
from unittest.mock import patch

import config

FLAGS = ('CODE_ENABLED', 'TASK_ENABLED', 'BUILD_ENABLED')


def _snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob('*')) if p.is_file()}


def _init(tmp_path: Path, name: str):
    projects = tmp_path / name
    with patch('tools.projects.PROJECTS_ROOT', str(projects)):
        from tools.projects import init_project_logic

        result = init_project_logic('Proj')
    return sorted(result.files_created), _snapshot(projects / 'Proj')


def test_init_project_groups_disabled_creates_identical_files_to_default(tmp_path, monkeypatch):
    for flag in FLAGS:
        monkeypatch.setattr(config, flag, True)
    default_files, default_tree = _init(tmp_path, 'default')

    for flag in FLAGS:
        monkeypatch.setattr(config, flag, False)
    off_files, off_tree = _init(tmp_path, 'all_off')

    assert default_files
    assert off_files == default_files
    assert off_tree == default_tree
