import logging

from services import adr_service, guideline_service, playbook_service, session_service
from utils.exceptions import ArtifactNotFoundError

import tools.artifacts

logger = logging.getLogger(__name__)

HARD_STOP_TEMPLATE_PATH = "docs/manuals/guidelines/hard_stop.md"
AUTO_ADVANCE_TEMPLATE_PATH = "docs/manuals/guidelines/auto_advance.md"

DEFAULT_HARD_STOP_TEXT = (
    "HARD STOP — await explicit human GO before proceeding.\nNext role on approval: {next_role}\n"
)
DEFAULT_AUTO_ADVANCE_TEXT = (
    "Auto-advance — no approval gate. On completion, set next_agent_role to: {next_role}\n"
)


def _build_next_step_section(project: str, profile) -> str:
    """Build the NEXT STEP section per REQ-03's decision tree.
    Returns '' for standalone roles (profile.next is None).
    Template text loads from project artifacts so each project can customize
    its own gate wording without a code deploy; falls back to a built-in
    default if the template artifact is missing.
    """
    if not profile or not profile.next:
        return ""

    template_path = (
        HARD_STOP_TEMPLATE_PATH if profile.requires_approval else AUTO_ADVANCE_TEMPLATE_PATH
    )
    default_text = (
        DEFAULT_HARD_STOP_TEXT if profile.requires_approval else DEFAULT_AUTO_ADVANCE_TEXT
    )
    try:
        template_text = tools.artifacts.read_artifact_logic(project, template_path)
    except ArtifactNotFoundError:
        template_text = default_text

    return f"\n=== NEXT STEP ===\n{template_text.format(next_role=profile.next)}"


def get_session_context_logic(project: str) -> str:
    """Read session state, detect the active pipeline phase, and return an assembled
    context bundle: session state + core guidelines + phase-appropriate guidelines +
    filtered foundational ADRs + role-linked skill stubs (=== PLAYBOOKS === section,
    only present when the detected role has skills registered in role_profiles.yaml).
    """
    session_ctx = session_service.load(project)
    guidelines = guideline_service.load(project, session_ctx.agent_role)
    if isinstance(guidelines, str):
        return guidelines  # error string from guideline_service

    adr_section = adr_service.load(project, session_ctx.agent_role)
    playbook_section = playbook_service.load(project, session_ctx.agent_role)

    playbook_section_text = ""
    if playbook_section:
        playbook_section_text = f"\n=== PLAYBOOKS ===\n{playbook_section}"

    next_step_section = _build_next_step_section(project, guidelines.profile)

    return (
        f"=== YOUR ROLE: {session_ctx.agent_role} ===\n\n"
        f"=== CORE GUIDELINES ===\n{guidelines.core_text}\n\n"
        f"=== PHASE GUIDELINES ({session_ctx.agent_role}) ===\n{guidelines.phase_text}\n\n"
        f"=== SESSION STATE ===\n{session_ctx.session_text}\n"
        f"=== SPEC:===\n{session_ctx.spec}\n"
        f"=== FOUNDATIONAL DECISIONS ===\n{adr_section}"
        f"{playbook_section_text}"
        f"{next_step_section}"
    )


def get_guideline_logic(project: str, role: str) -> str:
    """Assemble and return the full context bundle for a given agent role.

    Output format:
        === ROLE GUIDELINES ===
        {guideline_text}

        === FOUNDATIONAL DECISIONS ===
        {adr_summaries_joined}

        === PLAYBOOKS ===          <- only present when role has listed playbooks
        {playbook_content}
    """
    guidelines = guideline_service.load(project, role)
    if isinstance(guidelines, str):
        return guidelines  # error string

    adr_section = adr_service.load(project, role)
    playbook_section = playbook_service.load(project, role)

    parts = [
        f"=== ROLE GUIDELINES ===\n{guidelines.phase_text}",
        f"=== FOUNDATIONAL DECISIONS ===\n{adr_section}",
    ]
    if playbook_section:
        parts.append(f"=== PLAYBOOKS ===\n{playbook_section}")
    return "\n\n".join(parts) + "\n"
