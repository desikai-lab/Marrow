import os

import pytest

from tools.utils.filesystem_utils import (
    validate_artifact_path,
    validate_project_path,
)


def test_validate_artifact_path_readmeAtRoot_resolvesOutsideArtifactsFolder(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    prj_dir = tmp_path / "test_proj"
    prj_dir.mkdir()

    res = validate_artifact_path("test_proj", "README.md")
    expected = os.path.normpath(str(prj_dir / "README.md"))
    assert res == expected


def test_validate_artifact_path_normalRelPath_resolvesUnderArtifactsRoot(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    art_dir = tmp_path / "test_proj" / "artifacts"
    art_dir.mkdir(parents=True)

    res = validate_artifact_path("test_proj", "docs/spec.md")
    expected = os.path.normpath(str(art_dir / "docs" / "spec.md"))
    assert res == expected


def test_validate_artifact_path_traversalAttempt_raisesValueError(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    prj_dir = tmp_path / "test_proj"
    prj_dir.mkdir()

    with pytest.raises(ValueError, match="Path traversal attempt"):
        validate_artifact_path("test_proj", "../../outside.txt")


def test_validate_project_path_validProject_matchesProjectsRootJoin(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    prj_dir = tmp_path / "test_proj"
    prj_dir.mkdir()

    res = validate_project_path("test_proj")
    expected = os.path.normpath(str(prj_dir))
    assert res == expected


def test_validate_project_path_emptyProject_raisesValueError(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))

    with pytest.raises(ValueError, match="Invalid project path"):
        validate_project_path("")
