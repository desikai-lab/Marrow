import logging

from domain.responses import ArtifactSectionResult
from services.artifact_query_service import search_artifact_sections_logic
from services.role_profile_service import RoleProfileLoader
from tools.artifacts import read_artifact_logic

logger = logging.getLogger(__name__)

_PLAYBOOKS_PREFIX = "docs/playbooks/"
_loader = RoleProfileLoader()


async def search(project: str, query: str, limit: int = 3) -> list[ArtifactSectionResult]:
    """Semantic search scoped to docs/playbooks/.

    Returns up to `limit` ArtifactSectionResult entries whose path starts with
    'docs/playbooks/'. Returns an empty list if the folder is absent or has no
    indexed content. Tolerates malformed frontmatter — search is chunk-based.
    """
    results = await search_artifact_sections_logic(project, query, limit * 3)
    return [r for r in results if r.path.startswith(_PLAYBOOKS_PREFIX)][:limit]


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
    profile = loader.get_profile(yaml_text, agent_role)
    if isinstance(profile, str):
        # get_profile returns an error string when role is unknown
        logger.warning("playbook_service.load: %s", profile)
        return ""

    if not profile.playbooks:
        return ""

    parts: list[str] = []
    for pb_path in profile.playbooks:
        try:
            text = read_artifact_logic(project, pb_path, mode="full")
            parts.append(text)
        except Exception:
            logger.warning("playbook_service.load: could not read playbook '%s', skipping", pb_path)

    return "\n\n".join(parts)
