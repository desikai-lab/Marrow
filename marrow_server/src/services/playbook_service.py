import logging
import re

import yaml

from services.role_profile_service import RoleProfileLoader
from tools.artifacts import read_artifact_logic

logger = logging.getLogger(__name__)

_loader = RoleProfileLoader()

_FRONTMATTER_RE = re.compile(r"^---\n(.+?)\n---", re.DOTALL)


def _parse_stub(pb_path: str, text: str) -> str:
    text = text.replace("\r\n", "\n")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return f"- [{pb_path}]"
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return f"- [{pb_path}]"
    if not isinstance(fm, dict):
        return f"- [{pb_path}]"
    title = fm.get("title", pb_path)
    description = fm.get("description", "").strip()
    triggers = fm.get("triggers", [])
    scope = fm.get("scope", "")
    lines = [f"- {title} [{pb_path}]"]
    if description:
        lines.append(f"  {description}")
    if triggers:
        lines.append(f"  Triggers: {', '.join(triggers)}")
    if scope:
        lines.append(f"  Scope: {scope}")
    return "\n".join(lines)


def load(project: str, agent_role: str) -> str:
    """Return assembled playbook text for all playbooks listed under `agent_role`
    in role_profiles.yaml.

    Returns empty string when:
    - role_profiles.yaml is missing or malformed
    - role is unknown
    - the role's playbooks list is empty
    Logs a warning and skips any playbook file that cannot be read.
    Stays synchronous — called via asyncio.to_thread from the session tools layer.
    """

    from services.role_profile_service import RoleProfileLoader

    profiles_path = "docs/manuals/role_profiles.yaml"
    try:
        yaml_text = read_artifact_logic(project, profiles_path, mode="full")
    except Exception:
        logger.warning(
            "playbook_service.load: role_profiles.yaml not found for project '%s'", project
        )
        return ""

    loader = RoleProfileLoader()
    normalized_role = agent_role.lower().replace(" agent", "").strip()
    profile = loader.get_profile(yaml_text, normalized_role)
    if isinstance(profile, str):
        # get_profile returns an error string when role is unknown
        logger.warning("playbook_service.load: %s", profile)
        return ""

    if not profile.playbooks:
        return ""

    _HEADER = (
        "Use `read_project_artifacts` to load a skill by path when the task matches its triggers."
    )
    parts: list[str] = []
    for pb_path in profile.playbooks:
        try:
            text = read_artifact_logic(project, pb_path, mode="full")
            parts.append(_parse_stub(pb_path, text))
        except Exception:
            logger.warning("playbook_service.load: could not read playbook '%s', skipping", pb_path)
    if not parts:
        return ""
    return _HEADER + "\n\n" + "\n\n".join(parts)
