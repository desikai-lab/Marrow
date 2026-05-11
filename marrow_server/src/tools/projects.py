import os

from config import PROJECTS_ROOT


def list_projects_logic() -> list[str]:
    """Returns a list of all available project names."""
    if not os.path.exists(PROJECTS_ROOT): return []
    return [d for d in os.listdir(PROJECTS_ROOT) if os.path.isdir(os.path.join(PROJECTS_ROOT, d))]
