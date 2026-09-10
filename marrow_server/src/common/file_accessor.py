import os
import shutil
from collections.abc import Iterator
from typing import Protocol


class Accessor(Protocol):
    def read(self, absolute_path: str, encoding: str = "utf-8", errors: str = "strict") -> str: ...
    def write(
        self, absolute_path: str, content: str, encoding: str = "utf-8", newline: str | None = None
    ) -> None: ...
    def exists(self, absolute_path: str) -> bool: ...
    def copy(self, src_absolute_path: str, dest_absolute_path: str) -> None: ...
    def move(self, src_absolute_path: str, dest_absolute_path: str) -> None: ...
    def delete(self, absolute_path: str) -> None: ...
    def touch(self, absolute_path: str) -> None: ...
    def read_lines(
        self, absolute_path: str, encoding: str = "utf-8", errors: str = "strict"
    ) -> Iterator[str]: ...
    def listdir(self, absolute_path: str) -> list[str]: ...
    def isdir(self, absolute_path: str) -> bool: ...


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

    @staticmethod
    def copy(src_absolute_path: str, dest_absolute_path: str) -> None:
        os.makedirs(os.path.dirname(dest_absolute_path), exist_ok=True)
        shutil.copy2(src_absolute_path, dest_absolute_path)

    @staticmethod
    def move(src_absolute_path: str, dest_absolute_path: str) -> None:
        os.makedirs(os.path.dirname(dest_absolute_path), exist_ok=True)
        shutil.move(src_absolute_path, dest_absolute_path)

    @staticmethod
    def delete(absolute_path: str) -> None:
        if os.path.exists(absolute_path):
            os.remove(absolute_path)

    @staticmethod
    def touch(absolute_path: str) -> None:
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
        with open(absolute_path, "a"):
            os.utime(absolute_path, None)

    @staticmethod
    def read_lines(
        absolute_path: str, encoding: str = "utf-8", errors: str = "strict"
    ) -> Iterator[str]:
        with open(absolute_path, encoding=encoding, errors=errors) as f:
            yield from f

    @staticmethod
    def listdir(absolute_path: str) -> list[str]:
        return os.listdir(absolute_path)

    @staticmethod
    def isdir(absolute_path: str) -> bool:
        return os.path.isdir(absolute_path)
