import os
from typing import Protocol


class Accessor(Protocol):
    def read(self, absolute_path: str, encoding: str = "utf-8", errors: str = "strict") -> str: ...
    def write(
        self, absolute_path: str, content: str, encoding: str = "utf-8", newline: str | None = None
    ) -> None: ...
    def exists(self, absolute_path: str) -> bool: ...


class FileAccessor:
    @staticmethod
    def read(absolute_path: str, encoding: str = "utf-8", errors: str = "strict") -> str:
        with open(absolute_path, encoding=encoding, errors=errors) as f:
            return f.read()

    @staticmethod
    def write(
        absolute_path: str, content: str, encoding: str = "utf-8", newline: str | None = None
    ) -> None:
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
        with open(absolute_path, "w", encoding=encoding, newline=newline) as f:
            f.write(content)

    @staticmethod
    def exists(absolute_path: str) -> bool:
        return os.path.exists(absolute_path)
