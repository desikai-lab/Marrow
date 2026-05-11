from tools.utils.markdown_utils import extract_markdown_section


def validate_section_not_exists(content: str, section_name: str, rel_path: str):
    """Raises ValueError if the section already exists in the content."""
    section_text, _, _ = extract_markdown_section(content, section_name)
    if section_text is not None:
        raise ValueError(f"Section '{section_name}' already exists in artifact {rel_path}. Adding duplicates is not allowed.")
