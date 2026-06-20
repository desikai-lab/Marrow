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


def _parse_next_agent(session_text: str) -> str | None:
    match = re.search(r"next_agent_role[:\s\*]+(.+)", session_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    logger.warning("No next_agent_role found in session text.")
    return None


def load(project: str) -> SessionContext:
    """Read session.md and spec.md; parse phase and agent_role.
    Gracefully degrades on missing session.md (empty strings), but a missing or
    unparseable next_agent_role is always a hard error — there is no phase-based
    role guess anymore (see ADR-0036/ROLE-01).
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
        raise ValueError(
            "session.md is missing next_agent_role — cannot resolve agent role. "
            "Add 'next_agent_role: <RoleName>' to session.md."
        )

    phase = _parse_phase(session_text, warn=False)

    return SessionContext(
        session_text=session_text,
        spec=spec,
        phase=phase,
        agent_role=agent_role,
    )
