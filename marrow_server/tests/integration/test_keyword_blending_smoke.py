import os
import shutil

import pytest

from config import PROJECTS_ROOT
from storage.db import get_keyword_table, init_db
from storage.uow import UnitOfWork
from tools.artifact_pipeline import maybe_extract_keywords
from tools.utils.project_settings import ProjectSettings


@pytest.mark.asyncio
async def test_keyword_blending_end_to_end_smoke():
    project_name = "test_keyword_blending_smoke_proj"
    project_root = os.path.join(PROJECTS_ROOT, project_name)

    if os.path.exists(project_root):
        try:
            shutil.rmtree(project_root)
        except Exception:
            pass

    os.makedirs(project_root, exist_ok=True)
    os.makedirs(os.path.join(project_root, "artifacts"), exist_ok=True)

    try:
        # Write .settings file with LITERAL_EXTRACTION=on
        settings_file = os.path.join(project_root, ".settings")
        with open(settings_file, "w", encoding="utf-8") as f:
            f.write(f"SOURCE_ROOT={project_root}\nLITERAL_EXTRACTION=on\n")

        init_db(project_root)
        uow = UnitOfWork(project_root)

        # 1. Upsert a rich artifact with identifiers
        doc_path = "docs/sample.md"
        content = (
            "## Section 1\n"
            "This document handles issue TD4000238 and F4000249 feature work.\n"
            "Uses MemGPT and arXiv:2310.08560 for references.\n\n"
            "## Section 2\n"
            "Secondary notes for testing RRF fusion.\n"
        )
        updated_at = "2026-09-23T12:00:00"
        chunks = await uow.chunks.upsert_chunks(doc_path, content, updated_at)
        assert len(chunks) == 2

        # 2. Extract keywords using settings flag
        settings = ProjectSettings(literal_extraction=True)
        await maybe_extract_keywords(settings, uow.chunks, doc_path, chunks, updated_at)

        # 3. Verify keyword table populated
        kw_table = get_keyword_table(project_root)
        rows = kw_table.search().to_list()
        assert len(rows) == 2
        keywords_str = " ".join(r["keywords"] for r in rows)
        assert "td4000238" in keywords_str
        assert "f4000249" in keywords_str

        # 4. Search with LITERAL_EXTRACTION enabled
        search_results = await uow.chunks.semantic_search("TD4000238", limit=5)
        assert len(search_results) > 0
        assert search_results[0]["path"] == doc_path
        assert "match" in search_results[0]
    finally:
        if os.path.exists(project_root):
            try:
                shutil.rmtree(project_root)
            except Exception:
                pass
