class ProjectFileError(Exception):
    """Raised by ProjectPath.read()/write() on any I/O failure.
    Carries only relative_path — never the absolute path, never the
    underlying exception (see Architecture §2.1 / requirements.md §7 amendment b)."""

    def __init__(self, relative_path: str):
        self.relative_path = relative_path
        super().__init__(f"File operation failed: {relative_path}")
