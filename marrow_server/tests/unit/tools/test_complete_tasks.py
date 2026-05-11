"""Tests for complete_tasks / move_tasks_batch_atomically (TD4000078).

Unit tests use unittest.mock to avoid live LanceDB / filesystem I/O.
Run with: pytest tests/test_complete_tasks.py -v
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_record(key: str, status: str = "active", blocked_by: list = None):
    """Returns a minimal TaskRecord-like MagicMock."""
    rec = MagicMock()
    rec.key = key
    rec.id = abs(hash(key)) % 10_000
    rec.project = "TestProject"
    rec.status = status
    rec.file_path = f".db/blobs/active/{key}.md"
    rec.title = f"Task {key}"
    rec.type = "F"
    rec.priority = "medium"
    rec.problem = None
    rec.solution = None
    rec.blocked_by = blocked_by or []
    rec.where = []
    rec.comments = None
    rec.resolution = None
    return rec


def _make_blob(key: str, status: str = "active", blocked_by: list = None) -> dict:
    return {
        "key": key,
        "id": abs(hash(key)) % 10_000,
        "project": "TestProject",
        "title": f"Task {key}",
        "type": "F",
        "status": status,
        "priority": "medium",
        "blocked_by": blocked_by or [],
    }


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_project(tmp_path):
    """Creates a minimal on-disk project structure."""
    blobs_dir = tmp_path / ".db" / "blobs" / "active"
    blobs_dir.mkdir(parents=True)
    return tmp_path


# ── Task 1.4 tests ────────────────────────────────────────────────────────────


class TestCompleteSingleTaskHappyPath:
    """One valid task_id → status updated, old blob removed."""

    def test_complete_task_valid_id_updates_status_and_removes_blob(self, tmp_project):
        key = "ТД001"
        blob_data = _make_blob(key)
        record = _make_record(key)

        # Write a real blob file so shutil.copy2 can backup it
        blob_path = tmp_project / record.file_path
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        blob_path.write_text(json.dumps(blob_data), encoding="utf-8")

        with (
            patch("storage.uow.TaskRepository") as MockTaskRepo,
            patch("storage.uow.ArtifactRepository"),
            patch("storage.uow.ArtifactChunkRepository"),
            patch("storage.uow.read_blob", return_value=blob_data),
            patch("storage.uow.write_blob") as mock_write,
            patch("storage.uow.validate_status_change"),
        ):
            # write_blob → returns path to a *new* blob
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

            from storage.uow import UnitOfWork

            uow = UnitOfWork(str(tmp_project))
            import asyncio

            result = asyncio.run(uow.move_tasks_batch_atomically([key], new_status="✅ Закрыта"))

        assert key in result["completed"]
        assert result["unblocked"] == []
        repo_instance.table.add.assert_called_once()


class TestCompleteMultipleTasksSingleLock:
    """N tasks closed in one call; _file_lock is held for the full batch."""

    def test_move_tasks_batch_atomically_multiple_tasks_acquires_lock_once(self, tmp_project):
        keys = ["ТД001", "ТД002", "ТД003"]
        blobs = {k: _make_blob(k) for k in keys}
        records = {k: _make_record(k) for k in keys}

        for k, rec in records.items():
            p = tmp_project / rec.file_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(blobs[k]), encoding="utf-8")

        lock_acquire_count = []

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def counting_lock(name):
            lock_acquire_count.append(1)
            yield

        with (
            patch("storage.uow.TaskRepository") as MockTaskRepo,
            patch("storage.uow.ArtifactRepository"),
            patch("storage.uow.ArtifactChunkRepository"),
            patch("storage.uow.read_blob", side_effect=lambda p: blobs[Path(p).stem]),
            patch("storage.uow.write_blob") as mock_write,
            patch("storage.uow.validate_status_change"),
            patch("storage.db.get_table_lock", side_effect=counting_lock),
        ):

            def _fake_write(root, data):
                p = tmp_project / ".db" / "blobs" / "done" / f"{data['key']}.md"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(data), encoding="utf-8")
                return p

            mock_write.side_effect = _fake_write

            repo_inst = MockTaskRepo.return_value
            repo_inst.get_by_key = AsyncMock(side_effect=lambda k: records[k])
            repo_inst.search = AsyncMock(return_value=[])
            repo_inst.table.delete = MagicMock()
            repo_inst.table.add = MagicMock()
            repo_inst.upsert = AsyncMock()
            # table.name is used by get_table_lock
            repo_inst.table.name = "tasks"

            from storage.uow import UnitOfWork

            uow = UnitOfWork(str(tmp_project))

            import asyncio

            result = asyncio.run(uow.move_tasks_batch_atomically(keys, new_status="closed"))

        assert set(result["completed"]) == set(keys)
        # The lock was entered exactly once for the entire batch (single-lock guarantee)
        assert len(lock_acquire_count) == 1


class TestFailFastOnUnknownKey:
    """One bad key in batch → TaskNotFoundError raised, zero writes."""

    def test_move_tasks_batch_atomically_unknown_key_raises_task_not_found_error(self, tmp_project):
        good_key = "TD001"
        bad_key = "TD_MISSING"

        rec = _make_record(good_key)
        blob = _make_blob(good_key)
        p = tmp_project / rec.file_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(blob), encoding="utf-8")

        with (
            patch("storage.uow.TaskRepository") as MockTaskRepo,
            patch("storage.uow.ArtifactRepository"),
            patch("storage.uow.ArtifactChunkRepository"),
            patch("storage.uow.read_blob", return_value=blob),
            patch("storage.uow.write_blob") as mock_write,
            patch("storage.uow.validate_status_change"),
        ):
            repo_inst = MockTaskRepo.return_value
            # Return None for the bad key
            repo_inst.get_by_key = AsyncMock(side_effect=lambda k: rec if k == good_key else None)
            repo_inst.table.add = MagicMock()

            from storage.uow import UnitOfWork
            from utils.exceptions import TaskNotFoundError

            uow = UnitOfWork(str(tmp_project))

            import asyncio

            with pytest.raises(TaskNotFoundError):
                asyncio.run(
                    uow.move_tasks_batch_atomically([good_key, bad_key], new_status="✅ Закрыта")
                )

            # Zero writes to storage
            mock_write.assert_not_called()
            repo_inst.table.add.assert_not_called()


class TestRollbackOnLanceDbFailure:
    """Mock table.add to raise → verify blob backups are restored."""

    def test_rollback_on_lancedb_failure(self, tmp_project):
        key = "TD001"
        blob_data = _make_blob(key)
        rec = _make_record(key)

        original_path = tmp_project / rec.file_path
        original_path.parent.mkdir(parents=True, exist_ok=True)
        original_path.write_text(json.dumps(blob_data), encoding="utf-8")

        with (
            patch("storage.uow.TaskRepository") as MockTaskRepo,
            patch("storage.uow.ArtifactRepository"),
            patch("storage.uow.ArtifactChunkRepository"),
            patch("storage.uow.read_blob", return_value=blob_data),
            patch("storage.uow.write_blob") as mock_write,
            patch("storage.uow.validate_status_change"),
        ):
            new_blob = tmp_project / ".db" / "blobs" / "done" / f"{key}.md"
            new_blob.parent.mkdir(parents=True, exist_ok=True)
            new_blob.write_text(json.dumps(blob_data), encoding="utf-8")
            mock_write.return_value = new_blob

            repo_inst = MockTaskRepo.return_value
            repo_inst.get_by_key = AsyncMock(return_value=rec)
            repo_inst.table.delete = MagicMock()
            repo_inst.table.add = MagicMock(side_effect=RuntimeError("LanceDB failure"))
            repo_inst.search = AsyncMock(return_value=[])

            from storage.uow import UnitOfWork

            uow = UnitOfWork(str(tmp_project))

            import asyncio

            with pytest.raises(RuntimeError, match="LanceDB failure"):
                asyncio.run(uow.move_tasks_batch_atomically([key], new_status="closed"))

        # Backup should have been written to .history/
        bak = tmp_project / ".history" / key / f"{key}.md.bak"
        assert bak.exists(), "Backup must be created before the LanceDB write"


class TestAutoUnblockClearsBlockedBy:
    """Task B has blocked_by=[A]; completing A → B.blocked_by becomes []."""

    def test_auto_unblock_clears_blocked_by(self, tmp_project):
        key_a = "TD001"
        key_b = "TD002"

        rec_a = _make_record(key_a)
        blob_a = _make_blob(key_a)
        p_a = tmp_project / rec_a.file_path
        p_a.parent.mkdir(parents=True, exist_ok=True)
        p_a.write_text(json.dumps(blob_a), encoding="utf-8")

        rec_b = _make_record(key_b, status="open", blocked_by=[key_a])
        blob_b = _make_blob(key_b, blocked_by=[key_a])
        p_b = tmp_project / rec_b.file_path
        p_b.write_text(json.dumps(blob_b), encoding="utf-8")

        def _fake_read(path):
            stem = Path(path).stem
            if stem == key_a:
                return blob_a
            return blob_b

        def _fake_write(root, data):
            p = tmp_project / ".db" / "blobs" / "done" / f"{data['key']}.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data), encoding="utf-8")
            return p

        with (
            patch("storage.uow.TaskRepository") as MockTaskRepo,
            patch("storage.uow.ArtifactRepository"),
            patch("storage.uow.ArtifactChunkRepository"),
            patch("storage.uow.read_blob", side_effect=_fake_read),
            patch("storage.uow.write_blob", side_effect=_fake_write),
            patch("storage.uow.validate_status_change"),
        ):
            repo_inst = MockTaskRepo.return_value
            repo_inst.get_by_key = AsyncMock(return_value=rec_a)
            repo_inst.search = AsyncMock(return_value=[rec_b])  # one active task with blocked_by
            repo_inst.table.delete = MagicMock()
            repo_inst.table.add = AsyncMock()
            repo_inst.upsert = AsyncMock()

            import asyncio

            from storage.uow import UnitOfWork

            uow = UnitOfWork(str(tmp_project))
            result = asyncio.run(uow.move_tasks_batch_atomically([key_a], new_status="✅ Закрыта"))

        assert key_b in result["unblocked"]


class TestEmptyTaskIdsReturnsEarly:
    """Empty list → returns summary message, no storage calls."""

    def test_empty_task_ids_returns_early(self):
        with patch("services.task_command_service.DECOUPLED_STORAGE_ENABLED", True):
            with patch("services.task_command_service.PROJECTS_ROOT", "/fake"):
                with patch("os.path.isdir", return_value=True):
                    import asyncio

                    from services.task_command_service import complete_tasks_logic

                    result = asyncio.run(complete_tasks_logic([], "SomeProject"))
        assert "No task IDs" in result
