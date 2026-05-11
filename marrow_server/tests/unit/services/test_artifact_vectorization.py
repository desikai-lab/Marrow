import asyncio
import os
import shutil
import sys
import unittest
from datetime import datetime
from unittest.mock import patch

# Add project root to paths
sys.path.append(os.getcwd())

from config import DECOUPLED_STORAGE_ENABLED, PROJECTS_ROOT
from storage.uow import UnitOfWork
from tools.artifact_pipeline import (
    GroupingHandler,
    PipelineContext,
    ValidationHandler,
)
from tools.artifacts import search_project_artifacts_logic
from tools.utils.cleaner import ContentCleaner

FAKE_VECTOR = [0.1] * 384


class TestArtifactVectorization(unittest.TestCase):
    def setUp(self):
        self.project = "test_vec_internal"
        self.project_root = os.path.join(PROJECTS_ROOT, self.project)

        if os.path.exists(self.project_root):
            try:
                shutil.rmtree(self.project_root)
            except Exception:
                pass
        os.makedirs(self.project_root, exist_ok=True)
        # Artifacts usually reside in project root or /artifacts
        os.makedirs(os.path.join(self.project_root, "artifacts"), exist_ok=True)

        # Initialize database
        from storage.db import init_db

        init_db(self.project_root)

        # Mock embeddings globally for this test class
        self.embeddings_patcher = patch(
            "storage.repositories.artifact_repository.embeddings_manager.generate_vector",
            return_value=FAKE_VECTOR,
        )
        self.mock_generate_vector = self.embeddings_patcher.start()

    def tearDown(self):
        self.embeddings_patcher.stop()
        # On Windows, LanceDB sometimes holds file locks; attempt deletion
        try:
            if os.path.exists(self.project_root):
                shutil.rmtree(self.project_root)
        except Exception:
            pass


    def test_clean_noise_content_removes_metadata_and_logs(self):
        """Verifies cleaning content of noise (comments, logs)."""
        content = """
# Title
<!-- secret comment -->
> **Version: 1.0.0
> | Log: test
Some actual content.
"""

        cleaned = ContentCleaner.clean(content)
        self.assertNotIn("secret comment", cleaned)
        self.assertNotIn("Version: 1.0.0", cleaned)
        self.assertIn("Some actual content", cleaned)

    def test_grouping_handler_mixed_modes_sorts_chunks_before_sections(self):
        """Verifies sorting rules: chunks first, then by -start_line."""
        updates = [
            {"path": "file.md", "mode": "replace_section", "section_name": "S1", "content": "C1"},
            {
                "path": "file.md",
                "mode": "replace_chunk",
                "start_line": 10,
                "end_line": 12,
                "content": "CH1",
            },
            {
                "path": "file.md",
                "mode": "replace_chunk",
                "start_line": 5,
                "end_line": 6,
                "content": "CH2",
            },
        ]
        ctx = PipelineContext(self.project, updates)
        h = GroupingHandler()
        asyncio.run(h.handle(ctx))

        group = ctx.grouped_updates["file.md"]
        # Expected order: CH1 (start 10), CH2 (start 5), then S1
        self.assertEqual(group[0][1]["mode"], "replace_chunk", "Chunks must be first")
        self.assertEqual(group[0][1]["start_line"], 10, "Largest start_line first")
        self.assertEqual(group[1][1]["mode"], "replace_chunk")
        self.assertEqual(group[1][1]["start_line"], 5)
        self.assertEqual(group[2][1]["mode"], "replace_section")

    def test_save_project_artifacts_logic_chunk_updates_persists_correctly(self):
        """Integration test for the persistence pipeline (in-memory updates)."""
        path = "abc.md"
        abs_path = os.path.join(self.project_root, "artifacts", path)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")

        updates = [
            {
                "path": path,
                "mode": "replace_chunk",
                "start_line": 2,
                "end_line": 2,
                "content": "New Line 2",
            },
            {
                "path": path,
                "mode": "replace_chunk",
                "start_line": 4,
                "end_line": 4,
                "content": "New Line 4",
            },
        ]

        from tools.artifact_pipeline import save_project_artifacts_logic

        results = asyncio.run(save_project_artifacts_logic(self.project, updates))

        for r in results:
            self.assertEqual(r["status"], "success", f"Failed: {r.get('message')}")

        with open(abs_path, encoding="utf-8") as f:
            final = f.read()

        self.assertIn("New Line 2", final)
        self.assertIn("New Line 4", final)
        # Verify that Lines 1, 3, 5 are preserved
        self.assertIn("Line 1", final)
        self.assertIn("Line 3", final)
        self.assertIn("Line 5", final)

    def test_semantic_search_indexed_artifact_returns_relevant_result(self):
        """Verifies vector index operation and cascade search."""
        if not DECOUPLED_STORAGE_ENABLED:
            self.skipTest("Decoupled storage not enabled")

        path = "docs/search_test.md"
        content = "This is a very specific artifact about vector search engines and AI."
        updated = datetime.now().isoformat()

        uow = UnitOfWork(self.project_root)
        asyncio.run(uow.artifacts.upsert(path, content, updated))

        # 1. Direct semantic search
        results = asyncio.run(uow.artifacts.semantic_search("vector search", limit=1))
        self.assertTrue(len(results) > 0, "No results from semantic search")
        self.assertEqual(results[0]["record"].path, path)

        # 2. Cascade search (Semantic + Grep)
        cascade_results = asyncio.run(
            search_project_artifacts_logic(self.project, "specific artifact")
        )
        self.assertTrue(
            any(r["path"] == path for r in cascade_results), "Path not found in cascade search"
        )

    def test_validation_handler_invalid_mode_and_missing_path_returns_errors(self):
        """Verifies the validation handler."""
        updates = [
            {"path": "valid.md", "mode": "invalid_mode"},
            {"mode": "replace_file"},  # missing path
        ]
        ctx = PipelineContext(self.project, updates)
        h = ValidationHandler()
        asyncio.run(h.handle(ctx))

        self.assertEqual(ctx.results[0]["status"], "error")
        self.assertEqual(ctx.results[1]["status"], "error")


if __name__ == "__main__":
    unittest.main()
