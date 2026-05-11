import logging
import re

from tools.artifacts import read_artifact_logic
from utils.exceptions import ArtifactNotFoundError

logger = logging.getLogger(__name__)

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


def get_session_context_logic(project: str) -> str:
    """Read session state, detect the active pipeline phase, and return an assembled
    context bundle: session state + core guidelines + phase-appropriate guidelines.
    
    Fallback behaviour:
    - session_current.md missing → session section is empty; phase defaults to 1.
    - Phase field absent/unparseable → phase defaults to 1.
    - Core or phase guideline file missing → ArtifactNotFoundError propagated (hard infra gap).
    """
    # 1. Read session state — graceful degradation on missing file
    try:
        session_text = read_artifact_logic(project, "session.md")
        spec = read_artifact_logic(project, "spec.md")
    except ArtifactNotFoundError:
        logger.warning("session_current.md not found for project '%s'; proceeding with empty session.", project)
        session_text = ""
        spec = ""

    # 2. Detect current phase
    agent_role = _parse_next_agent(session_text)
    
    if agent_role == None:
        phase = _parse_phase(session_text)
        agent_role = _select_agent_role(phase)

    # 3. Select phase-specific guideline path
    guideline_path = GuidelinesFactory.get_guideline(agent_role)

    # 4. Read core guidelines — hard failure if missing
    core_text = read_artifact_logic(project, "docs/manuals/guidelines/core.md")

    # 5. Read phase-specific guidelines — hard failure if missing
    phase_text = read_artifact_logic(project, guideline_path)

    # 6. Assemble and return
    return (
        f"=== YOUR ROLE: {agent_role} ===\n\n"
        f"=== CORE GUIDELINES ===\n{core_text}\n\n"
        f"=== PHASE GUIDELINES ({agent_role}) ===\n{phase_text}\n\n"
        f"=== SESSION STATE ===\n{session_text}\n"
        f"=== SPEC:===\n{spec}\n"
    )

class GuidelinesFactory:
    _guidelines = {
        'Discovery Agent': "docs/manuals/guidelines/discovery.md",
        'Architecture Agent': "docs/manuals/guidelines/discovery.md",
        'Planning Agent': "docs/manuals/guidelines/planning.md",
        'Execution Agent': "docs/manuals/guidelines/execution.md"
    }
    
    @classmethod
    def get_guideline(cls, agent_role: str) -> str:
        if agent_role not in cls._guidelines:
            raise ValueError(f"Unknown pipeline role: '{agent_role}'")
        return cls._guidelines[agent_role]
    