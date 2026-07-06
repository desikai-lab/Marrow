import pytest
from domain.validators.section_exists import SectionNotExistsValidator
from utils.exceptions import ValidationError

CONTENT_WITH_SECTION = "# My Doc\n\n## Existing Section\n\nSome text here.\n"
CONTENT_WITHOUT_SECTION = "# My Doc\n\nNo sections here.\n"


def test_validate_section_exists_raises_ValidationError():
    validator = SectionNotExistsValidator(CONTENT_WITH_SECTION, "Existing Section", "doc.md")
    with pytest.raises(ValidationError):
        validator.validate()


def test_validate_section_missing_passes():
    validator = SectionNotExistsValidator(CONTENT_WITHOUT_SECTION, "Missing Section", "doc.md")
    validator.validate()  # Should not raise


def test_validate_section_case_insensitive_raises():
    validator = SectionNotExistsValidator(CONTENT_WITH_SECTION, "existing section", "doc.md")
    with pytest.raises(ValidationError):
        validator.validate()
