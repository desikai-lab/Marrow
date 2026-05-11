import pytest

from storage.db import get_chunk_table, init_db
from storage.uow import UnitOfWork


@pytest.fixture
def temp_project(tmp_path):
    project_root = str(tmp_path / "test_project")
    init_db(project_root)
    yield project_root


@pytest.mark.asyncio
async def test_semantic_search_indexed_sections_returns_best_matching_section(temp_project):
    path = "docs/test.md"
    content = """# Main

## Configuration Setup
To configure the system, set the DB_PATH environment variable.
It allows the system to locate the main SQLite database.

## Deployment Guide
Run docker-compose up -d to deploy the infrastructure.
Make sure ports 8080 and 5432 are free.
"""
    updated = "2026-04-06T12:00:00Z"

    # 1. Индексируем чанки
    uow = UnitOfWork(temp_project)
    await uow.chunks.upsert_chunks(path, content, updated, ext=".md")

    # 2. Проверяем, что в БД появились чанки
    table = get_chunk_table(temp_project)
    assert len(table.search().to_list()) == 2

    # 3. Выполняем семантический поиск
    results = await uow.chunks.semantic_search(
        "How do I start the containers with docker?", limit=1
    )

    assert len(results) == 1
    best_match = results[0]

    assert best_match["path"] == path
    assert best_match["section"] == "## Deployment Guide"
    assert best_match["start_line"] == 7
    assert best_match["end_line"] == 10
    assert "distance" in best_match

    # Проверяем поиск для другого чанка
    results_db = await uow.chunks.semantic_search("Where is the SQLite database path set?", limit=1)
    assert len(results_db) == 1
    assert results_db[0]["section"] == "## Configuration Setup"
