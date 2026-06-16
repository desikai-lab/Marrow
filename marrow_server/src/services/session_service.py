import logging
import re
from dataclasses import dataclass

import tools.artifacts
from utils.exceptions import ArtifactNotFoundError

logger = logging.getLogger(__name__)


@dataclass
class SessionContext:
    session_text: str
    spec: str
    phase: int
    agent_role: str


def _parse_phase(session_text: str, *, warn: bool = True) -> int:
    """Extract the current pipeline phase number from session_current.md text.

    Looks for a line matching 'Phase N' (case-insensitive, optional surrounding text).
    Returns 1 (discovery) if the field is absent or unparseable.
    Set warn=False when next_agent_role already resolved the role and the phase
    is only stored for informational purposes.
    """
    match = re.search(r"(?:Phase|Step)[:\s]+(\d+)", session_text, re.IGNORECASE)
    if match and isinstance(match.group(1), str) and match.group(1) != "":
        return int(match.group(1))
    if warn:
        logger.warning("No phase number found in session text; defaulting to phase 1 (discovery).")
    return 1


def _parse_next_agent(session_text: str) -> str:
    match = re.search(r"next_agent_role[:\s\*]+(.+)", session_text, re.IGNORECASE)
    if match:
        return match.group(1)
    logger.warning("No next agent found in session text; defaulting to phase 1 (discovery).")
    return None


def _select_agent_role(phase: int) -> str:
    """Map a pipeline phase number to the appropriate agent role display name.

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


def load(project: str) -> SessionContext:
    """Read session.md and spec.md; parse phase and agent_role.
    Gracefully degrades on missing session.md (empty strings, phase=1, role='Discovery Agent').
    """
    try:
        session_text = tools.artifacts.read_artifact_logic(project, "session.md")
        spec = tools.artifacts.read_artifact_logic(project, "spec.md")
    except ArtifactNotFoundError:
        logger.warning(
            "session.md not found for project '%s'; proceeding with empty session.", project
        )
        session_text = ""
        spec = ""

    agent_role = _parse_next_agent(session_text)

    if agent_role is None:
        # Role is derived from phase — warn if phase is missing.
        phase = _parse_phase(session_text, warn=True)
        agent_role = _select_agent_role(phase)
    else:
        # Role already resolved via next_agent_role; phase is informational only.
        phase = _parse_phase(session_text, warn=False)

    return SessionContext(
        session_text=session_text,
        spec=spec,
        phase=phase,
        agent_role=agent_role,
    )
