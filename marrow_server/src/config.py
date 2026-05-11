import os
import sys

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# --- CONFIGURATION ---
SECRET_TOKEN = os.getenv("SECRET_TOKEN")
if not SECRET_TOKEN:
    raise RuntimeError("SECRET_TOKEN is not set. Create a .env file with a SECRET_TOKEN variable.")

# --- Decoupled Storage & Vectors (Phase 1-3) ---
DECOUPLED_STORAGE_ENABLED = os.getenv("DECOUPLED_STORAGE_ENABLED", "false").lower() == "true"

# Phase 3: Embedding Settings
EMBEDDING_MODEL_CODE = os.getenv("EMBEDDING_MODEL_CODE", "BAAI/bge-small-en-v1.5")
EMBEDDING_MODEL_TEXT = os.getenv("EMBEDDING_MODEL_TEXT", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# Backward compatibility (as fallback or for generic text)
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", EMBEDDING_MODEL_TEXT)

EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "384"))
MAX_EMBED_CHARS = int(os.getenv("MAX_EMBED_CHARS", "2000"))
VECT_DEBOUNCE_SECONDS = float(os.getenv("VECT_DEBOUNCE_SECONDS", "0.5"))

# Priority: .env TASKS_DIR > local tests
TASKS_DIR_ENV = os.getenv("TASKS_DIR")
if TASKS_DIR_ENV:
    BASE_DIR = os.path.abspath(TASKS_DIR_ENV)
else:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "tests"))

# NEW: Projects Root
PROJECTS_ROOT = os.path.join(BASE_DIR, "projects")

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
        "done": os.path.join(project_dir, "backlog_done.yaml")
    }


def check_startup_config():
    """Checks startup configuration for the default project (YourProject)."""
    print("\n[Marrow] checking projects structure", file=sys.stderr)
    print(f"   PROJECTS_ROOT: {PROJECTS_ROOT}", file=sys.stderr)
    
    default_project = "YourProject"
    files = get_project_files(default_project)
    
    all_ok = True
    for key, path in files.items():
        exists = os.path.exists(path)
        status = "[OK]" if exists else "[ERR]"
        size = f"{os.path.getsize(path):,} bytes" if exists else "not found"
        print(f"   {status} [{default_project}:{key}] {os.path.basename(path)} -- {size}", file=sys.stderr)
        if not exists:
            all_ok = False
    
    # if not all_ok:
    print("\n   [WRN] Default project 'YourProject' files incomplete. Check migration status.", file=sys.stderr)
    # else:
    print(f"   [OK] Default project '{default_project}' ready.\n", file=sys.stderr)
