import logging
import re

import tools.artifacts
from utils.exceptions import ArtifactNotFoundError

from services.role_profile_service import RoleProfileLoader

logger = logging.getLogger(__name__)

ADR_INDEX_PATH = "docs/decisions/0000-index.md"


def _parse_foundational_adr_paths(index_text: str, agent_role: str = "") -> list[str]:
    section_match = re.search(
        r"##\s+Foundational ADRs.*?(\n.*?)(?=\n##|\Z)",
        index_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not section_match:
        return []

    section = section_match.group(1)
    role_filter = agent_role.strip().lower()

    paths = []
    for line in section.splitlines():
        href_match = re.search(r"\(adr/[\w\-]+\.md\)", line)
        if not href_match:
            continue
        cells = [c.strip() for c in line.split("|")]
        roles_cell = cells[4].lower() if len(cells) > 4 else ""
        if role_filter and roles_cell and roles_cell != "all":
            roles_list = [r.strip() for r in roles_cell.split(",")]
            if not any(r in role_filter for r in roles_list):
                continue
        paths.append(f"docs/decisions/{href_match.group(0)[1:-1]}")
    return paths


def _extract_adr_summary(adr_text: str, adr_path: str) -> str:
    match = re.search(
        r"##\s+Summary\s*\n(.*?)(?=\n##|\Z)",
        adr_text,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        title_match = re.search(r"^#\s+([^\n]+)", adr_text)
        title = title_match.group(1).strip() if title_match else adr_path
        summary_content = match.group(1).strip()
        return f"# {title}\n**Source:** `{adr_path}`\n\n{summary_content}"
    return adr_text


def load(project: str, agent_role: str = "") -> str:
    """Parse ADR index, load role-filtered ADR files, return assembled summary string.

    - agent_role="" → no role filter, all foundational ADRs returned (backward compat).
    - Missing ADR index → logs warning, returns empty string.
    - Missing individual ADR file → logs warning, skips that ADR (never raises).
    Returns the joined ADR summaries as a single string (separator: '\n\n---\n\n').
    """
    adr_parts: list[str] = []
    try:
        index_text = tools.artifacts.read_artifact_logic(project, ADR_INDEX_PATH)
    except ArtifactNotFoundError:
        logger.warning(
            "ADR index not found for project '%s' at '%s' — skipping foundational ADRs.",
            project,
            ADR_INDEX_PATH,
        )
        return ""

    all_paths = _parse_foundational_adr_paths(index_text)

    # Resolve specific ADR IDs for role if agent_role is provided
    adrs_to_load = None
    if agent_role:
        try:
            yaml_text = tools.artifacts.read_artifact_logic(
                project, "docs/manuals/role_profiles.yaml"
            )
            normalized_role = agent_role.lower().replace(" agent", "").strip()
            profile = RoleProfileLoader().get_profile(yaml_text, normalized_role)
            if not isinstance(profile, str):
                adrs_to_load = profile.adrs
        except ArtifactNotFoundError:
            logger.warning(
                "role_profiles.yaml not found for project '%s' when loading ADRs.", project
            )

    if adrs_to_load is not None:
        path_lookup: dict[str, str] = {}
        for p in all_paths:
            stem = p.split("/")[-1]
            adr_id = stem[:4]
            path_lookup[adr_id] = p

        for adr_id in adrs_to_load:
            adr_path = path_lookup.get(adr_id)
            if not adr_path:
                logger.warning(
                    "ADR id '%s' not found in index for project '%s' — skipping.",
                    adr_id,
                    project,
                )
                continue
            try:
                adr_parts.append(
                    _extract_adr_summary(
                        tools.artifacts.read_artifact_logic(project, adr_path), adr_path
                    )
                )
            except ArtifactNotFoundError:
                logger.warning("ADR file not found: %s — skipping.", adr_path)
    else:
        # Load all ADRs from the index directly
        for adr_path in all_paths:
            try:
                adr_parts.append(
                    _extract_adr_summary(
                        tools.artifacts.read_artifact_logic(project, adr_path), adr_path
                    )
                )
            except ArtifactNotFoundError:
                logger.warning("ADR file not found: %s — skipping.", adr_path)

    return "\n\n---\n\n".join(adr_parts)
