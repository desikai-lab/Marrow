import os
import shutil

from config import PROJECTS_ROOT
from domain.responses import ProjectInitResult
from utils.exceptions import BaseBacklogError, ValidationError

TEMPLATE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "project-template")
)


def list_projects_logic() -> list[str]:
    """Returns a list of all available project names."""
    if not os.path.exists(PROJECTS_ROOT):
        return []
    return [d for d in os.listdir(PROJECTS_ROOT) if os.path.isdir(os.path.join(PROJECTS_ROOT, d))]


def init_project_logic(project: str, template: str = "default") -> ProjectInitResult:
    """Moved from InitCommand.execute(). Single source of truth for project init."""
    if template != "default":
        raise ValidationError(f"Only template 'default' is supported; got: '{template}'")

    target = os.path.join(PROJECTS_ROOT, project)

    if os.path.exists(target):
        raise ValidationError(f"Project '{project}' already exists at: {target}")

    if not os.path.isdir(TEMPLATE_DIR):
        raise BaseBacklogError(f"Built-in template not found at: {TEMPLATE_DIR}")

    os.makedirs(PROJECTS_ROOT, exist_ok=True)
    shutil.copytree(TEMPLATE_DIR, target)

    files_created = sorted(
        os.path.relpath(os.path.join(root, f), target)
        for root, _, files in os.walk(target)
        for f in files
    )

    return ProjectInitResult(
        project=project,
        files_created=files_created,
    )
