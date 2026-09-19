import asyncio
import os
import shutil
import unittest
from datetime import datetime
from unittest.mock import patch

from config import PROJECTS_ROOT
from storage.uow import UnitOfWork

FAKE_VECTOR = [0.1] * 384


class TestArtifactChunkRepositoryScopedSearch(unittest.TestCase):
    def setUp(self):
        self.project = "test_chunk_scope_search_internal"
        self.project_root = os.path.join(PROJECTS_ROOT, self.project)
        if os.path.exists(self.project_root):
            shutil.rmtree(self.project_root, ignore_errors=True)
        os.makedirs(os.path.join(self.project_root, "artifacts"), exist_ok=True)

        from storage.db import init_db

        init_db(self.project_root)

        self.embeddings_patcher = patch(
            "storage.embeddings.embeddings_manager.generate_vector",
            return_value=FAKE_VECTOR,
        )
        self.mock_generate_vector = self.embeddings_patcher.start()

    def tearDown(self):
        self.embeddings_patcher.stop()
        shutil.rmtree(self.project_root, ignore_errors=True)

    def _index(self, uow, path, text="content"):
        asyncio.run(uow.chunks.upsert_chunks(path, f"# H1\n{text}", datetime.now().isoformat()))

    def test_semantic_search_no_scope_returns_all_indexed_chunks_unchanged(self):
        uow = UnitOfWork(self.project_root)
        self._index(uow, "docs/a.md")
        self._index(uow, "docs/features/active/F4000202/b.md")

        results = asyncio.run(uow.chunks.semantic_search("content", limit=10))

        assert {r["path"] for r in results} == {"docs/a.md", "docs/features/active/F4000202/b.md"}

    def test_semantic_search_single_scope_returns_only_in_scope_hits(self):
        uow = UnitOfWork(self.project_root)
        self._index(uow, "docs/a.md")
        self._index(uow, "docs/features/active/F4000202/b.md")

        results = asyncio.run(
            uow.chunks.semantic_search(
                "content", limit=10, scopes=["docs/features/active/F4000202"]
            )
        )

        assert {r["path"] for r in results} == {"docs/features/active/F4000202/b.md"}

    def test_semantic_search_multiple_scopes_ors_results_across_both(self):
        uow = UnitOfWork(self.project_root)
        self._index(uow, "docs/decisions/adr/0001.md")
        self._index(uow, "docs/features/active/F4000202/b.md")
        self._index(uow, "sessions/history.md")

        results = asyncio.run(
            uow.chunks.semantic_search(
                "content",
                limit=10,
                scopes=["docs/decisions/adr", "docs/features/active/F4000202"],
            )
        )

        assert {r["path"] for r in results} == {
            "docs/decisions/adr/0001.md",
            "docs/features/active/F4000202/b.md",
        }

    def test_semantic_search_sibling_prefix_scope_excludes_sibling_folder(self):
        uow = UnitOfWork(self.project_root)
        self._index(uow, "docs/features/active/F4000202/b.md")
        self._index(uow, "docs/features/active/F40002020-other-feature/c.md")

        results = asyncio.run(
            uow.chunks.semantic_search(
                "content", limit=10, scopes=["docs/features/active/F4000202"]
            )
        )

        assert {r["path"] for r in results} == {"docs/features/active/F4000202/b.md"}

    def test_semantic_search_scope_with_quote_and_wildcard_does_not_widen_match(self):
        uow = UnitOfWork(self.project_root)
        self._index(uow, "docs/a.md")
        self._index(uow, "docs/100%done/b.md")

        # A scope containing '%' must match only the literal directory name,
        # never act as a SQL wildcard that would also match 'docs/aXXXdone'.
        results = asyncio.run(
            uow.chunks.semantic_search("content", limit=10, scopes=["docs/100%done"])
        )

        assert {r["path"] for r in results} == {"docs/100%done/b.md"}

    def test_semantic_search_scope_with_no_matches_returns_empty_list(self):
        uow = UnitOfWork(self.project_root)
        self._index(uow, "docs/a.md")

        results = asyncio.run(
            uow.chunks.semantic_search("content", limit=10, scopes=["docs/nonexistent"])
        )

        assert results == []
