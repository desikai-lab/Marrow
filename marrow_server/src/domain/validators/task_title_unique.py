from utils.exceptions import ValidationError

from domain.validation import Validator


class TaskTitleUniqueValidator(Validator):
    """Raises ValidationError if new_title duplicates an existing task title (case-insensitive)."""

    def __init__(self, new_title: str, existing_tasks: list[dict], project: str) -> None:
        self._new_title = new_title
        self._existing = existing_tasks
        self._project = project

    def validate(self) -> None:
        clean = self._new_title.strip().lower()
        for task in self._existing:
            if task.get("title", "").strip().lower() == clean:
                raise ValidationError(
                    f"A task with title '{self._new_title}' already exists in project '{self._project}'.",
                    details={"title": self._new_title, "project": self._project},
                )
