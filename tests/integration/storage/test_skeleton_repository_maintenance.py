"""
Integration tests for SkeletonRepository maintenance operations.

These tests verify that lancedb[pylance] is correctly installed so that
cleanup_old_versions() and compact_files() do not raise:
    RuntimeError: The lance library is required to use this function.
    Please install with `pip install pylance`.

Regression coverage for B4000188.
"""
import datetime

import pytest

from config import EMBEDDING_DIMENSIONS
from storage.repositories.skeleton_repository import SkeletonRepository
from storage.entities import SkeletonChunkRecord


def _make_chunk(path: str = "test/file.py", project: str = "test-project") -> SkeletonChunkRecord:
    """Minimal valid SkeletonChunkRecord for seeding the skeleton table."""
    return SkeletonChunkRecord(
        path=path,
        project=project,
        chunk_type="file",
        chunk_name="file",
        skeleton_text="def foo(): pass",
        start_line=1,
        end_line=1,
        updated=datetime.datetime.utcnow().isoformat(),
        is_test=False,
        vector=[0.0] * EMBEDDING_DIMENSIONS,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cleanup_old_versions_does_not_raise_pylance_import_error(tmp_path):
    """cleanup_old_versions() must not raise the pylance ImportError (B4000188)."""
    project_root = str(tmp_path)
    repo = SkeletonRepository(project_root)

    # Seed at least one row so the code_skeleton_index table exists on disk;
    # cleanup_old_versions skips tables at version <= 1, so this call is
    # sufficient to prove the pylance code path is reachable.
    chunk = _make_chunk()
    await repo.upsert_file_chunks(
        path=chunk.path,
        project=chunk.project,
        records=[chunk],
    )

    # Must not raise "The lance library is required to use this function."
    await repo.cleanup_old_versions(older_than_hours=0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_compact_files_does_not_raise_pylance_import_error(tmp_path):
    """compact_files() must not raise the pylance ImportError (B4000188)."""
    project_root = str(tmp_path)
    repo = SkeletonRepository(project_root)

    # Seed one row so the skeleton table exists and compact_files has something to operate on.
    chunk = _make_chunk()
    await repo.upsert_file_chunks(
        path=chunk.path,
        project=chunk.project,
        records=[chunk],
    )

    # Must not raise "The lance library is required to use this function."
    await repo.compact_files()

