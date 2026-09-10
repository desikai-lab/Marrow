import os

import pytest

from tools.utils.filesystem_utils import (
    create_artifact_backup,
    get_artifact_history,
    recycle_file,
    restore_backup,
    validate_artifact_path,
    validate_project_path,
)


def test_validate_artifact_path_readmeAtRoot_resolvesOutsideArtifactsFolder(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    prj_dir = tmp_path / "test_proj"
    prj_dir.mkdir()

    assert validate_artifact_path("test_proj", "README.md") is True


def test_validate_artifact_path_normalRelPath_resolvesUnderArtifactsRoot(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    art_dir = tmp_path / "test_proj" / "artifacts"
    art_dir.mkdir(parents=True)

    assert validate_artifact_path("test_proj", "docs/spec.md") is True


def test_validate_artifact_path_traversalAttempt_returnsFalse(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    prj_dir = tmp_path / "test_proj"
    prj_dir.mkdir()

    assert validate_artifact_path("test_proj", "../../outside.txt") is False


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


def test_create_artifact_backup_existingFile_copiesIntoPerItemHistoryFolder(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    art_dir = tmp_path / "test_proj" / "artifacts" / "docs"
    art_dir.mkdir(parents=True)
    src_file = art_dir / "spec.md"
    src_file.write_text("content")

    create_artifact_backup("test_proj", "docs/spec.md")

    history_dir = tmp_path / "test_proj" / ".history" / "artifacts" / "docs" / "spec.md"
    backups = list(history_dir.glob("*.md"))
    assert len(backups) == 1
    assert backups[0].read_text() == "content"
    # NEW convention (TD4000220): filename is bare {timestamp}.ext -- the
    # per-item folder supplies identity, not the filename prefix.
    assert "spec" not in backups[0].stem


def test_create_artifact_backup_missingSourceFile_noOpsSilently(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    art_dir = tmp_path / "test_proj" / "artifacts"
    art_dir.mkdir(parents=True)

    create_artifact_backup("test_proj", "docs/missing.md")

    history_root = tmp_path / "test_proj" / ".history"
    assert not history_root.exists()


def test_recycle_file_existingFile_movesIntoRecycleBinRoot(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    art_dir = tmp_path / "test_proj" / "artifacts"
    art_dir.mkdir(parents=True)
    src_file = art_dir / "note.md"
    src_file.write_text("content")

    result = recycle_file("test_proj", "note.md")

    assert result == "File note.md moved to recycle bin."
    assert not src_file.exists()
    recycle_root = tmp_path / "test_proj" / ".recycle_bin"
    moved = list(recycle_root.glob("note_*.md"))
    assert len(moved) == 1


def test_recycle_file_missingFile_returnsNotFoundMessageWithoutRaising(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    art_dir = tmp_path / "test_proj" / "artifacts"
    art_dir.mkdir(parents=True)

    result = recycle_file("test_proj", "missing.md")

    assert result == "File missing.md not found."


def test_get_artifact_history_afterBackup_listsBareTimestampedBackup(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    art_dir = tmp_path / "test_proj" / "artifacts" / "docs"
    art_dir.mkdir(parents=True)
    (art_dir / "spec.md").write_text("content")
    create_artifact_backup("test_proj", "docs/spec.md")

    history = get_artifact_history("test_proj", "docs/spec.md")

    assert len(history) == 1
    assert history[0]["backup_name"].endswith(".md")
    assert not history[0]["backup_name"].startswith("spec")
    assert "date" in history[0]
    assert history[0]["size"] == len("content")


def test_get_artifact_history_noHistoryDir_returnsEmptyList(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    art_dir = tmp_path / "test_proj" / "artifacts"
    art_dir.mkdir(parents=True)

    assert get_artifact_history("test_proj", "docs/spec.md") == []


def test_get_artifact_history_doesNotLeakSiblingItemsBackups(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    art_dir = tmp_path / "test_proj" / "artifacts" / "docs"
    art_dir.mkdir(parents=True)
    (art_dir / "spec.md").write_text("a")
    (art_dir / "spec2.md").write_text("b")
    create_artifact_backup("test_proj", "docs/spec.md")
    create_artifact_backup("test_proj", "docs/spec2.md")

    assert len(get_artifact_history("test_proj", "docs/spec.md")) == 1


def test_restore_backup_validBackup_copiesBackupContentBackToOriginal(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    art_dir = tmp_path / "test_proj" / "artifacts" / "docs"
    art_dir.mkdir(parents=True)
    target = art_dir / "spec.md"
    target.write_text("v1")
    create_artifact_backup("test_proj", "docs/spec.md")
    history_dir = tmp_path / "test_proj" / ".history" / "artifacts" / "docs" / "spec.md"
    backup_name = next(history_dir.glob("*.md")).name
    target.write_text("v2")

    result = restore_backup("test_proj", "docs/spec.md", backup_name)

    assert result == f"Artifact docs/spec.md successfully restored from {backup_name}."
    assert target.read_text() == "v1"


def test_restore_backup_missingBackupName_raisesFileNotFoundError(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    art_dir = tmp_path / "test_proj" / "artifacts" / "docs"
    art_dir.mkdir(parents=True)
    (art_dir / "spec.md").write_text("v1")

    with pytest.raises(FileNotFoundError, match="Backup nonexistent.md not found"):
        restore_backup("test_proj", "docs/spec.md", "nonexistent.md")


def test_restore_backup_traversalInBackupName_raisesValueError(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    art_dir = tmp_path / "test_proj" / "artifacts" / "docs"
    art_dir.mkdir(parents=True)
    (art_dir / "spec.md").write_text("v1")

    with pytest.raises(ValueError, match="Invalid backup source"):
        restore_backup("test_proj", "docs/spec.md", "../../../etc/passwd")
