import os
import pytest
from tools.projects import init_project_logic
from utils.exceptions import ValidationError


@pytest.mark.asyncio
async def test_init_project_happy_path(tmp_path):
    from unittest.mock import patch
    projects_dir = tmp_path / "projects"

    with patch("tools.projects.PROJECTS_ROOT", str(projects_dir)):
        result = init_project_logic("test-integration")
        assert result.project == "test-integration"
        assert "workspace_path" not in result.model_dump()   # must NOT be exposed to agent
        assert len(result.files_created) > 0

        target_dir = projects_dir / "test-integration"
        assert (target_dir / "artifacts" / "session.md").exists()
        assert (target_dir / "artifacts" / "spec.md").exists()


@pytest.mark.asyncio
async def test_init_project_already_exists(tmp_path):
    from unittest.mock import patch
    projects_dir = tmp_path / "projects"
    (projects_dir / "duplicate").mkdir(parents=True)

    with patch("tools.projects.PROJECTS_ROOT", str(projects_dir)):
        with pytest.raises(ValidationError, match="already exists"):
            init_project_logic("duplicate")
