from abc import ABC, abstractmethod


class IntegrityHook(ABC):
    """Pre-save hook contract. Runs after path validation, before backup and
    before the SaveStrategy executes. Gives file-specific logic a chance to
    validate/repair content before it's written. Mirrors SaveStrategy's shape
    for consistency with the existing Strategy pattern in artifact_strategies.py.
    """

    @abstractmethod
    def validate_and_repair(self, project: str, rel_path: str, content: str, mode: str) -> str:
        """Return the (possibly repaired) content to actually persist."""
        ...


class ArtifactIntegrityRegistry:
    """Registry of pre-save integrity hooks, keyed by exact filename (case-insensitive).
    Unregistered filenames simply have no hook — save proceeds with content unchanged.
    Mirrors ArtifactStrategyFactory's dict-based classmethod dispatch pattern.
    """

    _hooks: dict[str, IntegrityHook] = {}

    @classmethod
    def register(cls, filename: str, hook: IntegrityHook) -> None:
        cls._hooks[filename.lower()] = hook

    @classmethod
    def get_hook(cls, rel_path: str) -> IntegrityHook | None:
        filename = rel_path.lower().split("/")[-1]
        return cls._hooks.get(filename)
