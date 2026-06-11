import pytest
from unittest.mock import patch, AsyncMock
import yaml

from services import playbook_service
from services.role_profile_service import RoleProfile, RoleProfileLoader
from domain.responses import ArtifactSectionResult


def test_load_yaml_missing_returns_empty():
    with patch("services.playbook_service.read_artifact_logic", side_effect=Exception("not found")):
        res = playbook_service.load("test_proj", "execution")
        assert res == ""


def test_load_unknown_role_returns_empty():
    yaml_content = "roles:\n  execution:\n    guideline: g.md\n"
    with patch("services.playbook_service.read_artifact_logic", return_value=yaml_content):
        res = playbook_service.load("test_proj", "planning")
        assert res == ""


def test_load_no_playbooks_returns_empty():
    yaml_content = "roles:\n  execution:\n    guideline: g.md\n    playbooks: []\n"
    with patch("services.playbook_service.read_artifact_logic", return_value=yaml_content):
        res = playbook_service.load("test_proj", "execution")
        assert res == ""


def test_load_reads_playbooks_successfully():
    yaml_content = "roles:\n  execution:\n    guideline: g.md\n    playbooks:\n      - docs/playbooks/pb1.md\n      - docs/playbooks/pb2.md\n"

    def mock_read(project, rel_path, mode="full"):
        if rel_path == "docs/manuals/role_profiles.yaml":
            return yaml_content
        elif rel_path == "docs/playbooks/pb1.md":
            return "pb1 content"
        elif rel_path == "docs/playbooks/pb2.md":
            return "pb2 content"
        raise Exception("unexpected path")

    with patch("services.playbook_service.read_artifact_logic", side_effect=mock_read):
        res = playbook_service.load("test_proj", "execution")
        assert res == "pb1 content\n\npb2 content"


def test_load_skips_failed_playbook_reads():
    yaml_content = "roles:\n  execution:\n    guideline: g.md\n    playbooks:\n      - docs/playbooks/pb1.md\n      - docs/playbooks/pb2.md\n"

    def mock_read(project, rel_path, mode="full"):
        if rel_path == "docs/manuals/role_profiles.yaml":
            return yaml_content
        elif rel_path == "docs/playbooks/pb1.md":
            return "pb1 content"
        else:
            raise Exception("simulate file read error")

    with patch("services.playbook_service.read_artifact_logic", side_effect=mock_read):
        res = playbook_service.load("test_proj", "execution")
        assert res == "pb1 content"



@pytest.mark.asyncio
async def test_search_returns_filtered_results():
    mock_results = [
        ArtifactSectionResult(path="docs/playbooks/pb1.md", section="Section 1", start_line=1, end_line=10, distance=0.1),
        ArtifactSectionResult(path="docs/not-playbooks/other.md", section="Section 2", start_line=1, end_line=10, distance=0.2),
        ArtifactSectionResult(path="docs/playbooks/pb2.md", section="Section 3", start_line=1, end_line=10, distance=0.3),
    ]
    with patch("services.playbook_service.search_artifact_sections_logic", new_callable=AsyncMock, return_value=mock_results):
        res = await playbook_service.search("test_proj", "query", limit=2)
        assert len(res) == 2
        assert res[0].path == "docs/playbooks/pb1.md"
        assert res[1].path == "docs/playbooks/pb2.md"
