import logging

from services import adr_service, guideline_service, playbook_service, session_service

logger = logging.getLogger(__name__)


def get_session_context_logic(project: str) -> str:
    """Read session state, detect the active pipeline phase, and return an assembled
    context bundle: session state + core guidelines + phase-appropriate guidelines.
    """
    session_ctx = session_service.load(project)
    guidelines = guideline_service.load(project, session_ctx.agent_role)
    if isinstance(guidelines, str):
        return guidelines  # error string from guideline_service

    adr_section = adr_service.load(project, session_ctx.agent_role)
    # playbook_service is called, but its output is reserved/discarded for now
    playbook_service.load(project, session_ctx.agent_role)

    return (
        f"=== YOUR ROLE: {session_ctx.agent_role} ===\n\n"
        f"=== CORE GUIDELINES ===\n{guidelines.core_text}\n\n"
        f"=== PHASE GUIDELINES ({session_ctx.agent_role}) ===\n{guidelines.phase_text}\n\n"
        f"=== SESSION STATE ===\n{session_ctx.session_text}\n"
        f"=== SPEC:===\n{session_ctx.spec}\n"
        f"=== FOUNDATIONAL DECISIONS ===\n{adr_section}\n"
    )


def get_guideline_logic(project: str, role: str) -> str:
    """Assemble and return the full context bundle for a given agent role.

    Output format:
        === ROLE GUIDELINES ===
        {guideline_text}

        === FOUNDATIONAL DECISIONS ===
        {adr_summaries_joined}
    """
    guidelines = guideline_service.load(project, role)
    if isinstance(guidelines, str):
        return guidelines  # error string

    adr_section = adr_service.load(project, role)

    return (
        f"=== ROLE GUIDELINES ===\n{guidelines.phase_text}\n\n"
        f"=== FOUNDATIONAL DECISIONS ===\n{adr_section}\n"
    )
