from tools.artifact_pipeline import DefaultPipeline
from tools.pipeline_base import PersistPipeline
from tools.session_pipeline import SessionPipeline


def _canonical(path: str) -> str:
    """Case-insensitive identity comparison, with leading './' and '/'
    variants normalized away -- 'Session.md', '/session.md', and
    './session.md' all compare equal. Scoped to identity/routing
    comparisons only; not a replacement for path_resolver's own
    sandbox/traversal validation."""
    while path.startswith("./") or path.startswith("/"):
        path = path[2:] if path.startswith("./") else path[1:]
    return path.lower()


class PipelineDispatcher:
    """Resolves the correct PersistPipeline for a relative path (ADR-0047 §2.1).

    A single hardcoded check today (session.md vs. everything else), matching
    architecture.md's explicit call-out that this is deliberately not a
    generalized per-path registry yet -- see architecture.md §4. Lives in its
    own module so PersistHandler (Task 4) depends on this file alone, not on
    DefaultPipeline's implementation module."""

    def __init__(self) -> None:
        self._session_pipeline: PersistPipeline = SessionPipeline()
        self._default_pipeline: PersistPipeline = DefaultPipeline()

    def get_pipeline(self, path: str) -> PersistPipeline:
        if _canonical(path) == "session.md":
            return self._session_pipeline
        return self._default_pipeline
