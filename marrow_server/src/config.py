import os

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# --- CONFIGURATION ---
SECRET_TOKEN = os.getenv("SECRET_TOKEN")
if not SECRET_TOKEN:
    raise RuntimeError("SECRET_TOKEN is not set. Create a .env file with a SECRET_TOKEN variable.")

# --- Embedding Settings ---

# Phase 3: Embedding Settings
EMBEDDING_MODEL_CODE = os.getenv("EMBEDDING_MODEL_CODE", "BAAI/bge-small-en-v1.5")
EMBEDDING_MODEL_TEXT = os.getenv(
    "EMBEDDING_MODEL_TEXT", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# Backward compatibility (as fallback or for generic text)
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", EMBEDDING_MODEL_TEXT)

EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "384"))
MAX_EMBED_CHARS = int(os.getenv("MAX_EMBED_CHARS", "2000"))

# Agent Profile Engine
AGENT_PROFILE_ENGINE_ENABLED: bool = (
    os.getenv("AGENT_PROFILE_ENGINE_ENABLED", "true").lower() == "true"
)
VECT_DEBOUNCE_SECONDS = float(os.getenv("VECT_DEBOUNCE_SECONDS", "0.5"))

# Priority: .env TASKS_DIR > local tests
TASKS_DIR_ENV = os.getenv("TASKS_DIR")
if TASKS_DIR_ENV:
    BASE_DIR = os.path.abspath(TASKS_DIR_ENV)
else:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "tests"))

# NEW: Projects Root
PROJECTS_ROOT = os.path.join(BASE_DIR, "projects")
DEFAULT_PROJECT = os.getenv("DEFAULT_PROJECT", "default")


def get_project_files(project: str) -> dict:
    """Returns file paths for a specific project."""
    project_dir = os.path.join(PROJECTS_ROOT, project)
    if not os.path.exists(project_dir):
        # Auto-create project directory if new
        os.makedirs(project_dir, exist_ok=True)

    return {
        "index": os.path.join(project_dir, "backlog_index.md"),
        "active": os.path.join(project_dir, "backlog_active.yaml"),
        "paused": os.path.join(project_dir, "backlog_paused.yaml"),
        "done": os.path.join(project_dir, "backlog_done.yaml"),
    }


def check_startup_config() -> None:
    """Logs startup readiness."""
    import logging

    logger = logging.getLogger("marrow.startup")
    existing = (
        [d for d in os.listdir(PROJECTS_ROOT) if os.path.isdir(os.path.join(PROJECTS_ROOT, d))]
        if os.path.exists(PROJECTS_ROOT)
        else []
    )
    if existing:
        logger.info(f"[Marrow] Projects loaded: {existing}")
    else:
        logger.warning(
            "[Marrow] No projects found. "
            "Call init_project via MCP or run: marrow-admin project-init --project <name>"
        )
