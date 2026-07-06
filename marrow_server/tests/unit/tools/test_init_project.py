from unittest.mock import patch

import pytest
from utils.exceptions import BaseBacklogError, ValidationError


def test_happy_path(tmp_path):
    template = tmp_path / "template"
    template.mkdir()
    (template / "session.md").write_text("# Session")
    (template / "spec.md").write_text("# Spec")

    with (
        patch("tools.projects.PROJECTS_ROOT", str(tmp_path / "projects")),
        patch("tools.projects.TEMPLATE_DIR", str(template)),
    ):
        from tools.projects import init_project_logic

        result = init_project_logic("myproject")

    assert result.project == "myproject"
    assert "workspace_path" not in result.model_dump()  # must NOT be exposed
    assert "session.md" in result.files_created
    assert "spec.md" in result.files_created


def test_project_already_exists(tmp_path):
    projects = tmp_path / "projects"
    (projects / "existing").mkdir(parents=True)

    with (
        patch("tools.projects.PROJECTS_ROOT", str(projects)),
        patch("tools.projects.TEMPLATE_DIR", str(tmp_path / "template")),
    ):
        from tools.projects import init_project_logic

        with pytest.raises(ValidationError, match="already exists"):
            init_project_logic("existing")


def test_template_missing(tmp_path):
    with (
        patch("tools.projects.PROJECTS_ROOT", str(tmp_path / "projects")),
        patch("tools.projects.TEMPLATE_DIR", str(tmp_path / "nonexistent")),
    ):
        from tools.projects import init_project_logic

        with pytest.raises(BaseBacklogError, match="template not found"):
            init_project_logic("myproject")


def test_unsupported_template(tmp_path):
    with (
        patch("tools.projects.PROJECTS_ROOT", str(tmp_path / "projects")),
        patch("tools.projects.TEMPLATE_DIR", str(tmp_path / "template")),
    ):
        from tools.projects import init_project_logic

        with pytest.raises(ValidationError, match="Only template 'default'"):
            init_project_logic("myproject", template="custom")
