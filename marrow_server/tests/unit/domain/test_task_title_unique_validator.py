import pytest

from domain.validators.task_title_unique import TaskTitleUniqueValidator
from utils.exceptions import ValidationError

EXISTING_TASKS = [
    {"title": "Build authentication"},
    {"title": "Fix login bug"},
]


def test_validate_duplicate_title_raises_ValidationError():
    validator = TaskTitleUniqueValidator("Build authentication", EXISTING_TASKS, "MyProject")
    with pytest.raises(ValidationError):
        validator.validate()


def test_validate_unique_title_passes():
    validator = TaskTitleUniqueValidator("Add dark mode", EXISTING_TASKS, "MyProject")
    validator.validate()  # Should not raise


def test_validate_title_case_insensitive_raises():
    validator = TaskTitleUniqueValidator("BUILD AUTHENTICATION", EXISTING_TASKS, "MyProject")
    with pytest.raises(ValidationError):
        validator.validate()
