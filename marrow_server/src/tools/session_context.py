import logging
import re

from tools.artifacts import read_artifact_logic
from utils.exceptions import ArtifactNotFoundError

logger = logging.getLogger(__name__)

# Stable address of the per-project ADR index. Content is parsed at runtime.
ADR_INDEX_PATH = "docs/decisions/0000-index.md"


def _parse_phase(session_text: str) -> int:
    """Extract the current pipeline phase number from session_current.md text.

    Looks for a line matching 'Phase N' (case-insensitive, optional surrounding text).
    Returns 1 (discovery) if the field is absent or unparseable.
    """
    match = re.search(r"(?:Phase|Step)[:\s]+(\d+)", session_text, re.IGNORECASE)
    if match and isinstance(match.group(1), str) and match.group(1) != "":
        return int(match.group(1))
    logger.warning("No phase number found in session text; defaulting to phase 1 (discovery).")
    return 1


def _parse_next_agent(session_text: str) -> str:
    match = re.search(r"next_agent_role[:\s\*]+(.+)", session_text, re.IGNORECASE)
    if match:
        return match.group(1)
    logger.warning("No next agent found in session text; defaulting to phase 1 (discovery).")
    return None


def _select_agent_role(phase: int) -> str:
    """Map a pipeline phase number to the appropriate phase-specific guideline file path.

    Phase 1–3   → Discovery Agent
    Phase 4–6   → Architecture Agent
    Phase 7–11  → Planning Agent
    Phase 12+   → Execution Agent
    """
    if phase >= 1 and phase <= 3:
        return "Discovery Agent"
    elif phase >= 4 and phase <= 6:
        return "Architecture Agent"
    elif phase >= 7 and phase <= 11:
        return "Planning Agent"
    else:
        return "Execution Agent"


def _parse_foundational_adr_paths(index_text: str, agent_role: str = "") -> list[str]:
    """Parse the 'Foundational ADRs' section of the ADR index and return
    project-relative paths for each listed ADR, optionally filtered by role.

    Filtering rules:
    - agent_role empty/blank: return all paths (backward compat).
    - roles cell absent, blank, or 'all': always include.
    - roles cell contains agent_role (case-insensitive): include.
    - Otherwise: exclude.
    Returns empty list if section absent. Never raises.
    """
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
        # cells[0]=empty, [1]=ID, [2]=Title, [3]=Status, [4]=Roles (optional)
        cells = [c.strip() for c in line.split("|")]
        roles_cell = cells[4].lower() if len(cells) > 4 else ""
        if role_filter and roles_cell and roles_cell != "all":
            roles_list = [r.strip() for r in roles_cell.split(",")]
            if not any(r in role_filter for r in roles_list):
                continue
        paths.append(f"docs/decisions/{href_match.group(0)[1:-1]}")
    return paths


def _extract_adr_summary(adr_text: str, adr_path: str) -> str:
    """Return the content of the '## Summary' section if present, prepended with
    the ADR title and source path.

    Falls back to the full ADR text if no Summary section exists,
    ensuring zero regression on ADRs that have not been updated.
    The header match is case-insensitive.
    """
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


def get_session_context_logic(project: str) -> str:
    """Read session state, detect the active pipeline phase, and return an assembled
    context bundle: session state + core guidelines + phase-appropriate guidelines.

    Fallback behaviour:
    - session.md missing → session section is empty; phase defaults to 1.
    - Phase field absent/unparseable → phase defaults to 1.
    - Core or phase guideline file missing → ArtifactNotFoundError propagated (hard infra gap).
    When AGENT_PROFILE_ENGINE_ENABLED=true, guideline and ADR resolution is delegated
    to RoleProfileLoader; role_profiles.yaml is the sole authority for per-role ADRs.
    """
    # 1. Read session state — graceful degradation on missing file
    try:
        session_text = read_artifact_logic(project, "session.md")
        spec = read_artifact_logic(project, "spec.md")
    except ArtifactNotFoundError:
        logger.warning(
            "session.md not found for project '%s'; proceeding with empty session.", project
        )
        session_text = ""
        spec = ""

    # 2. Detect current role
    agent_role = _parse_next_agent(session_text)

    if agent_role is None:
        phase = _parse_phase(session_text)
        agent_role = _select_agent_role(phase)

    # 3. Read core guidelines — always, both paths
    core_text = read_artifact_logic(project, "docs/manuals/guidelines/core.md")

    # 4. Delegate to Agent Profile Engine
    from services.role_profile_service import RoleProfileLoader

    # 4a. Load role_profiles.yaml
    try:
        yaml_text = read_artifact_logic(project, "docs/manuals/role_profiles.yaml")
    except ArtifactNotFoundError:
        return (
            f"Error: role_profiles.yaml not found for project '{project}'. "
            "Expected at docs/manuals/role_profiles.yaml."
        )

    # 4b. Resolve profile for detected role (normalize to match YAML keys)
    normalized_role = agent_role.lower().replace(" agent", "").strip()
    profile = RoleProfileLoader().get_profile(yaml_text, normalized_role)
    if isinstance(profile, str):
        return profile  # error string from loader (unknown role etc.)

    # 4c. Read phase guideline from profile
    try:
        phase_text = read_artifact_logic(project, profile.guideline)
    except ArtifactNotFoundError:
        return f"Error: guideline file not found: {profile.guideline}"

    # 4d. Resolve ADR paths from index — flat lookup only, no role filter
    adr_parts: list[str] = []
    try:
        index_text = read_artifact_logic(project, ADR_INDEX_PATH)
        all_paths = _parse_foundational_adr_paths(index_text)  # no role arg → returns all
        path_lookup: dict[str, str] = {}
        for p in all_paths:
            stem = p.split("/")[-1]
            adr_id = stem[:4]
            path_lookup[adr_id] = p

        for adr_id in profile.adrs:
            adr_path = path_lookup.get(adr_id)
            if not adr_path:
                logger.warning(
                    "APE: ADR id '%s' not found in index for project '%s' — skipping.",
                    adr_id,
                    project,
                )
                continue
            try:
                adr_parts.append(
                    _extract_adr_summary(read_artifact_logic(project, adr_path), adr_path)
                )
            except ArtifactNotFoundError:
                logger.warning("APE: ADR file not found: %s — skipping.", adr_path)
    except ArtifactNotFoundError:
        logger.warning(
            "ADR index not found for project '%s' at '%s' — skipping foundational ADRs.",
            project,
            ADR_INDEX_PATH,
        )
    adr_section = "\n\n---\n\n".join(adr_parts)

    return (
        f"=== YOUR ROLE: {agent_role} ===\n\n"
        f"=== CORE GUIDELINES ===\n{core_text}\n\n"
        f"=== PHASE GUIDELINES ({agent_role}) ===\n{phase_text}\n\n"
        f"=== SESSION STATE ===\n{session_text}\n"
        f"=== SPEC:===\n{spec}\n"
        f"=== FOUNDATIONAL DECISIONS ===\n{adr_section}\n"
    )


def get_guideline_logic(project: str, role: str) -> str:
    """Assemble and return the full context bundle for a given agent role.

    Output format:
        === ROLE GUIDELINES ===
        {guideline_text}

        === FOUNDATIONAL DECISIONS ===
        {adr_summaries_joined}

    Returns an error string (never raises to MCP layer) on:
    - Unknown role or malformed role_profiles.yaml
    - Missing guideline or ADR file
    """
    from services.role_profile_service import RoleProfileLoader

    # 1. Load role_profiles.yaml
    try:
        yaml_text = read_artifact_logic(project, "docs/manuals/role_profiles.yaml")
    except ArtifactNotFoundError:
        return (
            f"Error: role_profiles.yaml not found for project '{project}'. "
            "Expected at docs/manuals/role_profiles.yaml."
        )

    # 2. Resolve profile for requested role
    profile = RoleProfileLoader().get_profile(yaml_text, role)
    if isinstance(profile, str):
        return profile  # error string from loader

    # 3. Read guideline text
    try:
        guideline_text = read_artifact_logic(project, profile.guideline)
    except ArtifactNotFoundError:
        return f"Error: guideline file not found: {profile.guideline}"

    # 4. Resolve ADR paths via index and collect summaries
    adr_parts: list[str] = []
    try:
        index_text = read_artifact_logic(project, ADR_INDEX_PATH)
        all_paths = _parse_foundational_adr_paths(index_text)  # no role filter — full index
        path_lookup: dict[str, str] = {}
        for p in all_paths:
            stem = p.split("/")[-1]  # e.g. "0007-pipeline-standard.md"
            adr_id = stem[:4]  # first 4 chars = ID
            path_lookup[adr_id] = p

        for adr_id in profile.adrs:
            adr_path = path_lookup.get(adr_id)
            if not adr_path:
                logger.warning(
                    "ADR id '%s' not found in index for project '%s' — skipping.",
                    adr_id,
                    project,
                )
                continue
            try:
                adr_text = read_artifact_logic(project, adr_path)
                adr_parts.append(_extract_adr_summary(adr_text, adr_path))
            except ArtifactNotFoundError:
                logger.warning("ADR file not found: %s — skipping.", adr_path)
    except ArtifactNotFoundError:
        logger.warning("ADR index not found for project '%s' — skipping ADRs.", project)

    adr_section = "\n\n---\n\n".join(adr_parts)
    return (
        f"=== ROLE GUIDELINES ===\n{guideline_text}\n\n"
        f"=== FOUNDATIONAL DECISIONS ===\n{adr_section}\n"
    )
