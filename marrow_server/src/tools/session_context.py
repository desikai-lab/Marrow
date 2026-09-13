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


def _resolve_from_session(project: str) -> tuple[str, str | None, str | None]:
    """Resolution strategy: read role + context from session.md.

    Returns (role, session_text, spec_text).
    Reads session.md via session_service.load — the only place in this
    module that touches session.md.
    """
    ctx = session_service.load(project)
    return ctx.agent_role, ctx.session_text, ctx.spec


def _resolve_from_role_param(project: str, role: str) -> tuple[str, str | None, str | None]:
    """Resolution strategy: use caller-supplied role name; never read session.md.

    Returns (role, None, spec_text).
    spec.md is read directly via read_artifact_logic; ArtifactNotFoundError
    propagates to @mcp_error_handler (consistent with session_service failures
    on the default path).
    """
    spec = tools.artifacts.read_artifact_logic(project, "spec.md")
    return role, None, spec


class ContextBundleBuilder:
    """Assembles the get_session_context response string.

    Fluent setters control which optional sections are included.
    Required sections (role header, core/phase guidelines, ADRs) are
    always present and passed at construction time.
    """

    def __init__(
        self,
        role: str,
        guidelines,
        adr_section: str,
        playbook_section: str,
    ) -> None:
        self._role = role
        self._guidelines = guidelines
        self._adr_section = adr_section
        self._playbook_section = playbook_section
        self._session_state: str | None = None
        self._spec: str | None = None

    def with_session_state(self, text: str) -> "ContextBundleBuilder":
        self._session_state = text
        return self

    def with_spec(self, text: str) -> "ContextBundleBuilder":
        self._spec = text
        return self

    def build(self, project: str) -> str:
        parts: list[str] = [
            f"=== YOUR ROLE: {self._role} ===\n\n",
            f"=== CORE GUIDELINES ===\n{self._guidelines.core_text}\n\n",
            f"=== PHASE GUIDELINES ({self._role}) ===\n{self._guidelines.phase_text}\n\n",
        ]
        if self._session_state is not None:
            parts.append(f"=== SESSION STATE ===\n{self._session_state}\n")
        if self._spec is not None:
            parts.append(f"=== SPEC:===\n{self._spec}\n")
        parts.append(f"=== FOUNDATIONAL DECISIONS ===\n{self._adr_section}")
        if self._playbook_section:
            parts.append(f"\n=== PLAYBOOKS ===\n{self._playbook_section}")
        next_step = _build_next_step_section(project, self._guidelines.profile)
        if next_step:
            parts.append(next_step)
        return "".join(parts)


def get_session_context_logic(project: str, start_role: str | None = None) -> str:
    """Read session state (or resolve a named role directly), detect the active
    pipeline phase, and return an assembled context bundle.

    When start_role is None (default): role and context are resolved from
    session.md; SESSION STATE and SPEC sections are included.

    When start_role is provided: the named role is resolved directly without
    reading session.md; SESSION STATE is omitted; SPEC is read independently.
    An unrecognised start_role returns an error string listing valid roles.
    """
    # --- 1. Resolve role + raw context via the appropriate strategy ---
    if start_role is None:
        role, session_text, spec_text = _resolve_from_session(project)
    else:
        role, session_text, spec_text = _resolve_from_role_param(project, start_role)

    # --- 2. Load shared services (identical for both strategies) ---
    guidelines = guideline_service.load(project, role)
    if isinstance(guidelines, str):
        return guidelines  # error string: unknown role, lists valid names (REQ-04)

    adr_section = adr_service.load(project, role)
    playbook_section = playbook_service.load(project, role)

    # --- 3. Assemble response via Builder ---
    builder = ContextBundleBuilder(role, guidelines, adr_section, playbook_section)
    if session_text is not None:
        builder.with_session_state(session_text)  # omitted on start_role path (REQ-07)
    if spec_text is not None:
        builder.with_spec(spec_text)  # always present on both paths (REQ-06)
    return builder.build(project)


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
