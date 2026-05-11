import asyncio
import os
import shutil
import unittest

from config import EMBEDDING_DIMENSIONS, PROJECTS_ROOT
from services.skeleton_query_service import _build_tree, get_project_map_logic
from storage.db import init_db
from storage.entities import SkeletonChunkRecord
from storage.repositories.skeleton_repository import SkeletonRepository


class TestSkel11Improvements(unittest.TestCase):
    def setUp(self):
        self.project = "test_skel11"
        self.project_root = os.path.join(PROJECTS_ROOT, self.project)
        if os.path.exists(self.project_root):
            shutil.rmtree(self.project_root, ignore_errors=True)
        init_db(self.project_root)
        self.repo = SkeletonRepository(self.project_root)

        # Test Data
        self.records = [
            # File
            SkeletonChunkRecord(
                path="src/main.py",
                project=self.project,
                chunk_type="file",
                chunk_name="main.py",
                skeleton_text="",
                start_line=0,
                end_line=100,
                updated="2026-04-11T12:00:00Z",
                vector=[0.1] * EMBEDDING_DIMENSIONS,
                is_test=False,
            ),
            # Class
            SkeletonChunkRecord(
                path="src/main.py",
                project=self.project,
                chunk_type="class",
                chunk_name="BaseClass",
                skeleton_text="class BaseClass:",
                start_line=10,
                end_line=30,
                updated="2026-04-11T12:00:00Z",
                vector=[0.2] * EMBEDDING_DIMENSIONS,
                is_test=False,
            ),
            # Method
            SkeletonChunkRecord(
                path="src/main.py",
                project=self.project,
                chunk_type="method",
                chunk_name="BaseClass.run",
                skeleton_text="    def run(self):",
                start_line=15,
                end_line=25,
                updated="2026-04-11T12:00:00Z",
                vector=[0.3] * EMBEDDING_DIMENSIONS,
                is_test=False,
            ),
            # Test File
            SkeletonChunkRecord(
                path="tests/test_main.py",
                project=self.project,
                chunk_type="file",
                chunk_name="test_main.py",
                skeleton_text="",
                start_line=0,
                end_line=50,
                updated="2026-04-11T12:00:00Z",
                vector=[0.4] * EMBEDDING_DIMENSIONS,
                is_test=True,
            ),
        ]
        asyncio.run(self.repo.upsert_file_chunks("src/main.py", self.project, self.records[:3]))
        asyncio.run(
            self.repo.upsert_file_chunks("tests/test_main.py", self.project, [self.records[3]])
        )

    def tearDown(self):
        if os.path.exists(self.project_root):
            shutil.rmtree(self.project_root, ignore_errors=True)

    def test_get_file_skeleton_chunks_depth_one_excludes_methods(self):
        # Depth 1: No methods
        chunks = asyncio.run(
            self.repo.get_file_skeleton_chunks("src/main.py", self.project, depth=1)
        )
        types = [c["chunk_type"] for c in chunks]
        self.assertIn("class", types)
        self.assertNotIn("method", types)
        # Should strip text at depth 1
        self.assertNotIn(
            "skeleton_text", chunks[chunks[0]["chunk_type"] == "class"]
        )  # Wait, class index check
        for c in chunks:
            self.assertNotIn("skeleton_text", c)

        # Depth 2: Includes methods
        chunks = asyncio.run(
            self.repo.get_file_skeleton_chunks("src/main.py", self.project, depth=2)
        )
        types = [c["chunk_type"] for c in chunks]
        self.assertIn("method", types)
        # Should NOT strip text at depth 2 (signatures are kept)
        self.assertIn(
            "skeleton_text", chunks[2]
        )  # method is at index 2 (0:file, 1:class, 2:method)

    def test_get_file_skeleton_chunks_depth_zero_summary_only_strips_skeleton_text(self):
        # Depth 0 + summary_only
        chunks = asyncio.run(
            self.repo.get_file_skeleton_chunks(
                "src/main.py", self.project, depth=0, summary_only=True
            )
        )
        for c in chunks:
            self.assertNotIn("skeleton_text", c)

    def test_semantic_search_include_tests_false_excludes_test_files(self):
        # include_tests=False (default)
        results = asyncio.run(
            self.repo.semantic_search(
                [0.0] * EMBEDDING_DIMENSIONS, project=self.project, include_tests=False
            )
        )
        paths = [r["path"] for r in results]
        self.assertIn("src/main.py", paths)
        self.assertNotIn("tests/test_main.py", paths)

        # include_tests=True
        results = asyncio.run(
            self.repo.semantic_search(
                [0.0] * EMBEDDING_DIMENSIONS, project=self.project, include_tests=True
            )
        )
        paths = [r["path"] for r in results]
        self.assertIn("tests/test_main.py", paths)

    def test_semantic_search_root_path_filter_scopes_results_to_prefix(self):
        results = asyncio.run(
            self.repo.semantic_search(
                [0.0] * EMBEDDING_DIMENSIONS, project=self.project, root_path="src/"
            )
        )
        paths = [r["path"] for r in results]
        self.assertTrue(all(p.startswith("src/") for p in paths))
        self.assertIn("src/main.py", paths)
        self.assertNotIn("tests/test_main.py", paths)

    def test_get_project_map_logic_indexed_files_returns_correct_tree_structure(self):
        # Test tree builder helper
        paths = ["src/a.py", "src/b.py", "tests/t1.py"]
        tree = _build_tree(paths, max_depth=2)
        self.assertIn("src/", tree["structure"])
        self.assertIn("a.py", tree["structure"]["src/"])
        self.assertIn("b.py", tree["structure"]["src/"])
        self.assertIn("tests/", tree["structure"])

        # Test logic
        m = asyncio.run(get_project_map_logic(self.project, depth=2))
        self.assertIn("src/", m["structure"])
        self.assertIn("main.py", m["structure"]["src/"])


if __name__ == "__main__":
    unittest.main()
