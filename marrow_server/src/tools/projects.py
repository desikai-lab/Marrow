import logging
import os
import shutil

import config as _config
from common import path_resolver
from config import PROJECTS_ROOT
from domain.responses import ProjectInitResult
from utils.exceptions import BaseBacklogError, ValidationError

_logger = logging.getLogger(__name__)

TEMPLATE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "project-template")
)

DEFAULT_STARTING_ROLE = "Discovery Agent"
INIT_STARTING_ROLE = "Init Agent"

# Written over the copied session.md when the code or task group is off. The structure is the
# template's session.md; only the role and the briefing differ. No tool names (ADR-0055).
_INIT_SESSION_MD = """# Session State — {project}
**Last updated:** YYYY-MM-DD
**Phase:** 0 — Init
**Current Task:** One-time adaptation check
**next_agent_role:** Init Agent

## ✅ Completed This Session
- Project initialized from Marrow template.

## 📂 Active Feature Bundle
[None]

## 📝 Init Agent Briefing
This project was created on a server where some tools are switched off, so the shipped guidelines may mention tools you do not have. Run Protocol B of your guideline: infer which tools exist, confirm with the human, adapt the guidelines minimally and log every change. When the human gives GO, hand over to the Discovery Agent. `spec.md` still contains FILL_IN markers that Discovery needs filled in.
"""


def list_projects_logic() -> list[str]:
    """Returns a list of all available project names."""
    if not os.path.exists(PROJECTS_ROOT):
        return []
    return [d for d in os.listdir(PROJECTS_ROOT) if os.path.isdir(os.path.join(PROJECTS_ROOT, d))]


def _disabled_group_count() -> int:
    """Number of guideline-relevant tool groups (CODE, TASK) switched off (read at call time).

    BUILD is ignored on purpose: it is experimental and no shipped guideline refers to it."""
    flags = (_config.CODE_ENABLED, _config.TASK_ENABLED)
    return sum(1 for enabled in flags if not enabled)


def _apply_starting_role(project: str) -> str:
    """Choose the first role of a freshly copied project (F4000303, ADR-0056).

    Nothing off: the template session.md already starts at the Discovery Agent.
    A group off: write the Init Agent session.md. No checks, no error path: init must
    always leave the user with a project they can start."""
    if _disabled_group_count() == 0:
        return DEFAULT_STARTING_ROLE
    # Same path API as every artifact write: sandboxed ProjectPath, engine IO options.
    path_resolver.get_path(project, "session.md").write(_INIT_SESSION_MD.format(project=project))
    return INIT_STARTING_ROLE


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
    starting_role = _apply_starting_role(project)

    files_created = sorted(
        os.path.relpath(os.path.join(root, f), target)
        for root, _, files in os.walk(target)
        for f in files
    )

    _logger.info("[init] project=%s starting_role=%s", project, starting_role)
    return ProjectInitResult(
        project=project,
        files_created=files_created,
        starting_role=starting_role,
    )
