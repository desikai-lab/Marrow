import os
import shutil
import unittest
import asyncio
from storage.entities import SkeletonChunkRecord
from storage.repositories.skeleton_repository import SkeletonRepository
from storage.db import init_db
from config import PROJECTS_ROOT, EMBEDDING_DIMENSIONS


class TestSkeletonRepository(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.project = "test_skeleton_repo"
        self.project_root = os.path.join(PROJECTS_ROOT, self.project)
        if os.path.exists(self.project_root):
            shutil.rmtree(self.project_root, ignore_errors=True)
        init_db(self.project_root)
        self.repo = SkeletonRepository(self.project_root)
        
        # Insert test data
        self.records = [
            SkeletonChunkRecord(
                path="src/main.py",
                project=self.project,
                chunk_type="function",
                chunk_name="process",
                skeleton_text="def process(): pass",
                start_line=10,
                end_line=15,
                updated="2026-04-10T12:00:00Z",
                vector=[0.0] * EMBEDDING_DIMENSIONS
            ),
            SkeletonChunkRecord(
                path="src/main.py",
                project=self.project,
                chunk_type="class",
                chunk_name="Processor",
                skeleton_text="class Processor: pass",
                start_line=1,
                end_line=5,
                updated="2026-04-10T12:00:00Z",
                vector=[0.0] * EMBEDDING_DIMENSIONS
            ),
            SkeletonChunkRecord(
                path="src/other.py",
                project=self.project,
                chunk_type="class",
                chunk_name="Other",
                skeleton_text="class Other: pass",
                start_line=1,
                end_line=5,
                updated="2026-04-10T12:00:00Z",
                vector=[0.0] * EMBEDDING_DIMENSIONS
            )
        ]
        await self.repo.upsert_file_chunks("src/main.py", self.project, self.records[:2])
        await self.repo.upsert_file_chunks("src/other.py", self.project, self.records[2:])

    async def asyncTearDown(self):
        if os.path.exists(self.project_root):
            shutil.rmtree(self.project_root, ignore_errors=True)

    async def test_get_file_skeleton_chunks_valid_path_returns_sorted_chunks_without_vector(self):
        chunks = await self.repo.get_file_skeleton_chunks("src/main.py", self.project)
        
        # Should return exactly 2 chunks (excluding other.py)
        self.assertEqual(len(chunks), 2)
        
        # Should be sorted chronologically by start_line
        self.assertEqual(chunks[0]["chunk_name"], "Processor")
        self.assertEqual(chunks[0]["start_line"], 1)
        self.assertEqual(chunks[1]["chunk_name"], "process")
        self.assertEqual(chunks[1]["start_line"], 10)
        
        # Should strip vector
        self.assertNotIn("vector", chunks[0])
        self.assertNotIn("vector", chunks[1])
