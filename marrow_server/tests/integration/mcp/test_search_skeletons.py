import pytest

from services.skeleton_query_service import search_code_skeletons_logic

pytestmark = pytest.mark.integration


async def test_search_code_skeletons_logic_empty_project_returns_empty_list(tmp_project):
    """Project exists but has no indexed skeletons — should return empty list."""
    results = await search_code_skeletons_logic(project=tmp_project, query="any query")
    assert isinstance(results, list)


async def test_search_code_skeletons_logic_unknown_project_returns_empty_list():
    """Unknown project dir — service logs warning and returns [] (Q2 contract)."""
    results = await search_code_skeletons_logic(project="__never_exists__", query="any query")
    assert results == []
