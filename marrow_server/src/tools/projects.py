import os
from typing import List
from config import PROJECTS_ROOT
from tools.utils.filesystem_utils import validate_project_path

def list_projects_logic() -> List[str]:
    """Returns a list of all available project names."""
    if not os.path.exists(PROJECTS_ROOT): return []
    return [d for d in os.listdir(PROJECTS_ROOT) if os.path.isdir(os.path.join(PROJECTS_ROOT, d))]
