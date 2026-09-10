import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from storage.uow import UnitOfWork


def _make_record(key: str, status: str = "active"):
    rec = MagicMock()
    rec.key = key
    rec.id = 123
    rec.project = "test_project"
    rec.status = status
    rec.file_path = f".db/blobs/active/{key}.md"
    rec.title = f"Task {key}"
    rec.type = "F"
    rec.priority = "medium"
    rec.problem = None
    rec.solution = None
    rec.blocked_by = []
    rec.where = []
    rec.comments = None
    rec.resolution = None
    return rec


def _make_blob(key: str, status: str = "active") -> dict:
    return {
        "key": key,
        "id": 123,
        "project": "test_project",
        "title": f"Task {key}",
        "type": "F",
        "status": status,
        "priority": "medium",
        "blocked_by": [],
    }


@pytest.fixture()
def tmp_project(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    project_dir = tmp_path / "test_project"
    blobs_dir = project_dir / ".db" / "blobs" / "active"
    blobs_dir.mkdir(parents=True)
    return project_dir


@pytest.mark.asyncio
async def test_update_task_atomically_still_succeeds_after_lock_migration(tmp_project):
    key = "TD001"
    blob_data = _make_blob(key)
    record = _make_record(key)

    with (
        patch("storage.uow.TaskRepository") as MockTaskRepo,
        patch("storage.uow.ArtifactRepository"),
        patch("storage.uow.ArtifactChunkRepository"),
        patch("storage.uow.read_blob", return_value=blob_data),
        patch("storage.uow.write_blob") as mock_write,
    ):
        mock_write.return_value = tmp_project / record.file_path
        repo_instance = MockTaskRepo.return_value
        repo_instance.get_by_key = AsyncMock(return_value=record)
        repo_instance.upsert = AsyncMock()
        repo_instance.table.name = "tasks"

        uow = UnitOfWork(str(tmp_project))
        result = await uow.update_task_atomically(key, {"title": "Updated Task"})

        assert result is not None
        mock_write.assert_called_once()
        repo_instance.upsert.assert_called_once()


@pytest.mark.asyncio
async def test_move_tasks_batch_atomically_still_succeeds_after_lock_migration(tmp_project):
    key = "TD001"
    blob_data = _make_blob(key)
    record = _make_record(key)

    # Write a real blob file so shutil.copy2 can back it up
    blob_path = tmp_project / record.file_path
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    blob_path.write_text(json.dumps(blob_data), encoding="utf-8")

    with (
        patch("storage.uow.TaskRepository") as MockTaskRepo,
        patch("storage.uow.ArtifactRepository"),
        patch("storage.uow.ArtifactChunkRepository"),
        patch("storage.uow.read_blob", return_value=blob_data),
        patch("storage.uow.write_blob") as mock_write,
        patch("storage.uow.StatusChangeValidator"),
    ):
        new_blob = tmp_project / ".db" / "blobs" / "done" / f"{key}.md"
        new_blob.parent.mkdir(parents=True, exist_ok=True)
        new_blob.write_text("{}", encoding="utf-8")
        mock_write.return_value = new_blob

        repo_instance = MockTaskRepo.return_value
        repo_instance.get_by_key = AsyncMock(return_value=record)
        repo_instance.search = AsyncMock(return_value=[])  # no active tasks to unblock
        repo_instance.table.delete = MagicMock()
        repo_instance.table.add = MagicMock()
        repo_instance.to_index_row = MagicMock()
        repo_instance.table.name = "tasks"

        uow = UnitOfWork(str(tmp_project))
        result = await uow.move_tasks_batch_atomically([key], new_status="done")

        assert key in result["completed"]
        assert result["unblocked"] == []


@pytest.mark.asyncio
async def test_update_task_atomically_writesTimestampedBackupUnderTasksNamespace(tmp_project):
    key = "TD001"
    blob_data = _make_blob(key)
    record = _make_record(key)

    # Pre-seed real blob file so the backup copy actually runs
    blob_path = tmp_project / record.file_path
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    blob_path.write_text(json.dumps(blob_data), encoding="utf-8")

    with (
        patch("storage.uow.TaskRepository") as MockTaskRepo,
        patch("storage.uow.ArtifactRepository"),
        patch("storage.uow.ArtifactChunkRepository"),
        patch("storage.uow.read_blob", return_value=blob_data),
        patch("storage.uow.write_blob") as mock_write,
    ):
        mock_write.return_value = tmp_project / record.file_path
        repo_instance = MockTaskRepo.return_value
        repo_instance.get_by_key = AsyncMock(return_value=record)
        repo_instance.upsert = AsyncMock()
        repo_instance.table.name = "tasks"

        uow = UnitOfWork(str(tmp_project))
        await uow.update_task_atomically(key, {"title": "Updated 1"})

        history_dir = tmp_project / ".history" / "tasks" / ".db" / "blobs" / "active" / f"{key}.md"
        backups = list(history_dir.glob("*.md"))
        assert len(backups) == 1

        import asyncio as _asyncio
        await _asyncio.sleep(1)  # ensure distinct timestamp
        await uow.update_task_atomically(key, {"title": "Updated 2"})

        backups = list(history_dir.glob("*.md"))
        assert len(backups) == 2


@pytest.mark.asyncio
async def test_moveTasksBatchAtomically_usesTasksNamespaceHistoryDir(tmp_project):
    key = "TD001"
    blob_data = _make_blob(key)
    record = _make_record(key)
    blob_path = tmp_project / record.file_path
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    blob_path.write_text(json.dumps(blob_data), encoding="utf-8")

    with (
        patch("storage.uow.TaskRepository") as MockTaskRepo,
        patch("storage.uow.ArtifactRepository"),
        patch("storage.uow.ArtifactChunkRepository"),
        patch("storage.uow.StatusChangeValidator"),
        patch("storage.uow.read_blob", return_value=blob_data),
    ):
        new_blob = tmp_project / ".db" / "blobs" / "done" / f"{key}.md"
        new_blob.parent.mkdir(parents=True, exist_ok=True)
        new_blob.write_text(json.dumps(blob_data), encoding="utf-8")
        with patch("storage.uow.write_blob", return_value=new_blob):
            repo_instance = MockTaskRepo.return_value
            repo_instance.get_by_key = AsyncMock(return_value=record)
            repo_instance.search = AsyncMock(return_value=[])
            repo_instance.table.delete = MagicMock()
            repo_instance.table.add = MagicMock()
            repo_instance.to_index_row = MagicMock()
            repo_instance.table.name = "tasks"

            uow = UnitOfWork(str(tmp_project))
            await uow.move_tasks_batch_atomically([key], new_status="done")

    history_dir = tmp_project / ".history" / "tasks" / record.file_path
    backups = list(history_dir.glob("*.md"))
    assert len(backups) == 1
    assert not blob_path.exists()


@pytest.mark.asyncio
async def test_moveTasksBatchAtomically_rollbackOnFailure_restoresFromTimestampedBackup(tmp_project):
    key = "TD001"
    blob_data = _make_blob(key)
    record = _make_record(key)
    blob_path = tmp_project / record.file_path
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    original_bytes = json.dumps(blob_data)
    blob_path.write_text(original_bytes, encoding="utf-8")

    with (
        patch("storage.uow.TaskRepository") as MockTaskRepo,
        patch("storage.uow.ArtifactRepository"),
        patch("storage.uow.ArtifactChunkRepository"),
        patch("storage.uow.StatusChangeValidator"),
        patch("storage.uow.read_blob", return_value=blob_data),
    ):
        new_blob = tmp_project / ".db" / "blobs" / "done" / f"{key}.md"
        new_blob.parent.mkdir(parents=True, exist_ok=True)
        new_blob.write_text("{}", encoding="utf-8")
        with patch("storage.uow.write_blob", return_value=new_blob):
            repo_instance = MockTaskRepo.return_value
            repo_instance.get_by_key = AsyncMock(return_value=record)
            repo_instance.table.delete = MagicMock(side_effect=RuntimeError("lancedb boom"))
            repo_instance.table.name = "tasks"

            uow = UnitOfWork(str(tmp_project))
            with pytest.raises(RuntimeError):
                await uow.move_tasks_batch_atomically([key], new_status="done")

    assert blob_path.read_text(encoding="utf-8") == original_bytes


@pytest.mark.asyncio
async def test_backupOriginal_writesTimestampedFileUnderTasksNamespace(tmp_project):
    key = "TD001"
    record = _make_record(key)
    orig_path = tmp_project / record.file_path
    orig_path.parent.mkdir(parents=True, exist_ok=True)
    orig_path.write_text("content-v1", encoding="utf-8")

    uow = UnitOfWork(str(tmp_project))
    from common.path_resolver import ResourceKind, get_path
    orig_pp = get_path(str(tmp_project), record.file_path, ResourceKind.ROOT)

    backup_pp = await uow._backup_original(record, orig_pp)

    assert backup_pp.read() == "content-v1"


@pytest.mark.asyncio
async def test_writeUpdatedBlob_returnsRecordWithNewStatusAndResolution(tmp_project):
    key = "TD001"
    record = _make_record(key)
    full_data = _make_blob(key)
    new_blob = tmp_project / ".db" / "blobs" / "done" / f"{key}.md"
    new_blob.parent.mkdir(parents=True, exist_ok=True)
    new_blob.write_text("{}", encoding="utf-8")

    with patch("storage.uow.write_blob", return_value=new_blob):
        uow = UnitOfWork(str(tmp_project))
        new_record = await uow._write_updated_blob(
            record, full_data, "done", "fixed", "2026-01-01T00:00:00"
        )

    assert new_record.status == "done"
    assert new_record.resolution == "fixed"


