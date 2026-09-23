import pytest


def test_reciprocalRankFusion_bothLanesHaveResults_mergesOnKey():
    from storage.repositories.artifact_repository import _reciprocal_rank_fusion
    vector = [
        {"path": "a.md", "start_line": 1, "end_line": 5, "section": "s", "distance": 0.1},
        {"path": "b.md", "start_line": 1, "end_line": 5, "section": "s", "distance": 0.2},
    ]
    keyword = [
        {"path": "b.md", "start_line": 1, "end_line": 5, "section": "s", "distance": 0.0},
        {"path": "c.md", "start_line": 1, "end_line": 5, "section": "s", "distance": 0.0},
    ]
    results = _reciprocal_rank_fusion(vector, keyword, limit=5)
    assert results[0]["path"] == "b.md"  # b.md in both lanes => highest RRF score
    assert results[0]["match"] == "both"


def test_reciprocalRankFusion_onlyVectorResults_matchIsVector():
    from storage.repositories.artifact_repository import _reciprocal_rank_fusion
    vector = [{"path": "a.md", "start_line": 1, "end_line": 5, "section": "s", "distance": 0.1}]
    results = _reciprocal_rank_fusion(vector, [], limit=5)
    assert results[0]["match"] == "vector"


def test_reciprocalRankFusion_limitRespected():
    from storage.repositories.artifact_repository import _reciprocal_rank_fusion
    vector = [
        {"path": f"file{i}.md", "start_line": i, "end_line": i+1, "section": "s", "distance": float(i)}
        for i in range(10)
    ]
    results = _reciprocal_rank_fusion(vector, [], limit=3)
    assert len(results) <= 3


def test_reciprocalRankFusion_emptyBothLanes_returnsEmpty():
    from storage.repositories.artifact_repository import _reciprocal_rank_fusion
    assert _reciprocal_rank_fusion([], [], limit=5) == []


@pytest.mark.asyncio
async def test_semanticSearch_flagOff_keywordLaneNeverCalled():
    from unittest.mock import AsyncMock, MagicMock, patch
    mock_settings = MagicMock()
    mock_settings.literal_extraction = False
    with patch("tools.utils.project_settings.load_project_settings", return_value=mock_settings), \
         patch("asyncio.to_thread", new=AsyncMock(return_value=[])):
        from storage.repositories.artifact_repository import ArtifactChunkRepository
        repo = ArtifactChunkRepository.__new__(ArtifactChunkRepository)
        repo.project_root = "/fake"
        repo.table = MagicMock()
        repo._keyword_lane_search = AsyncMock()
        await repo.semantic_search("test query", limit=5)
        repo._keyword_lane_search.assert_not_called()


@pytest.mark.asyncio
async def test_semanticSearch_keywordLaneFails_degradesGracefully():
    from unittest.mock import AsyncMock, MagicMock, patch
    mock_settings = MagicMock()
    mock_settings.literal_extraction = True
    vector_hit = {"path": "a.md", "start_line": 1, "end_line": 5, "section": "s", "_distance": 0.1}
    with patch("tools.utils.project_settings.load_project_settings", return_value=mock_settings), \
         patch("asyncio.to_thread", new=AsyncMock(return_value=[vector_hit])):
        from storage.repositories.artifact_repository import ArtifactChunkRepository
        repo = ArtifactChunkRepository.__new__(ArtifactChunkRepository)
        repo.project_root = "/fake"
        repo.table = MagicMock()
        repo._keyword_lane_search = AsyncMock(side_effect=Exception("lancedb error"))
        # Should not raise exception
        results = await repo.semantic_search("test query", limit=5)
        assert len(results) == 1
        assert results[0]["path"] == "a.md"
