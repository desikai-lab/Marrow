import logging
from dataclasses import dataclass

import tools.artifacts
from services.role_profile_service import RoleProfileLoader
from utils.exceptions import ArtifactNotFoundError

logger = logging.getLogger(__name__)


@dataclass
class GuidelineBundle:
    core_text: str
    phase_text: str


def load(project: str, agent_role: str) -> GuidelineBundle | str:
    """Load core.md and role-specific guideline via RoleProfileLoader.
    Returns GuidelineBundle on success, or an error string on failure
    (missing yaml, unknown role, missing guideline file).
    The agent_role is normalized internally (lowercase, strip ' agent' suffix).
    """
    core_text = tools.artifacts.read_artifact_logic(project, "docs/manuals/guidelines/core.md")

    try:
        yaml_text = tools.artifacts.read_artifact_logic(project, "docs/manuals/role_profiles.yaml")
    except ArtifactNotFoundError:
        return (
            f"Error: role_profiles.yaml not found for project '{project}'. "
            "Expected at docs/manuals/role_profiles.yaml."
        )

    # Resolve profile for detected role (normalize to match YAML keys)
    normalized_role = agent_role.lower().replace(" agent", "").strip()
    profile = RoleProfileLoader().get_profile(yaml_text, normalized_role)
    if isinstance(profile, str):
        return profile  # error string from loader (unknown role etc.)

    try:
        phase_text = tools.artifacts.read_artifact_logic(project, profile.guideline)
    except ArtifactNotFoundError:
        return f"Error: guideline file not found: {profile.guideline}"

    return GuidelineBundle(core_text=core_text, phase_text=phase_text)
