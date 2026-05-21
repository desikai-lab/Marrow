from domain.validation import Validator
from utils.exceptions import ValidationError


class SectionNotExistsValidator(Validator):
    """Raises ValidationError if the named section already exists in content."""

    def __init__(self, content: str, section_name: str, rel_path: str) -> None:
        self._content = content
        self._section_name = section_name
        self._rel_path = rel_path

    def validate(self) -> None:
        from tools.utils.markdown_utils import extract_markdown_section  # noqa: PLC0415

        section_text, _, _ = extract_markdown_section(self._content, self._section_name)
        if section_text is not None:
            raise ValidationError(
                f"Section '{self._section_name}' already exists in artifact {self._rel_path}.",
                details={"section": self._section_name, "path": self._rel_path},
            )
