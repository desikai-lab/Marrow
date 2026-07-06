"""
Domain exception hierarchy for Marrow.

All business-logic errors must inherit from BaseBacklogError so that
mcp_error_handler can distinguish them from unexpected system errors.
"""


class BaseBacklogError(Exception):
    """Base exception for all domain errors in Marrow."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ProjectNotFoundError(BaseBacklogError):
    """Project directory not found under PROJECTS_ROOT."""

    pass


class TaskNotFoundError(BaseBacklogError):
    """Task with the given key not found in LanceDB index."""

    pass


class ArtifactNotFoundError(BaseBacklogError):
    """Artifact file not found in the project storage."""

    pass


class InvalidPathError(BaseBacklogError):
    """Path contains unsafe symbols or escapes the project_root boundary."""

    pass


class DomainProtectionError(BaseBacklogError):
    """Operation violates a domain protection rule (e.g. overwriting a protected file)."""

    pass


class ValidationError(BaseBacklogError):
    """Business-rule validation failed (e.g. duplicate task title, invalid status transition)."""

    pass


class SourceAccessDisabledError(BaseBacklogError):
    """Raised when SOURCE_ROOT is not configured for the project."""

    pass


class SourceFileError(BaseBacklogError):
    """Raised for binary files, oversized files, or unreadable source files."""

    pass


class StorageTimeoutError(BaseBacklogError):
    """Raised when acquiring a table lock exceeds its configured timeout."""

    pass
