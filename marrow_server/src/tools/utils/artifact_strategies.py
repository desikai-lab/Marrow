import os
from abc import ABC, abstractmethod
from typing import Literal

from domain.validators.section_exists import SectionNotExistsValidator

from tools.utils.markdown_utils import (
    clean_section_name,
    extract_markdown_section,
    find_all_sections,
    strip_duplicated_header,
)


# --- HELPER ---
def apply_read_filters(
    text: str,
    max_chars: int | None,
    skip_chars: int,
    line_numbers: bool,
    start_line: int = 1,
    direction: Literal["begin", "end"] = "begin",
) -> str:
    """Applies pagination (skip/max) and optional line numbering.
    If max_chars=0 or None — no limit is applied.

    If direction="end" and max_chars > 0, automatically calculates skip_chars
    so that the last max_chars characters of the result are returned."""
    lines = text.splitlines()

    # 0. Adjust skip_chars for reading from the end (F48)
    if direction == "end" and max_chars is not None and max_chars > 0:
        total_len = 0
        for i, line in enumerate(lines, start_line):
            line_with_num = f"{i}: {line}" if line_numbers else line
            total_len += len(line_with_num) + 1  # +1 for \n

        # Shift skip_chars to show the last max_chars characters,
        # accounting for any user-supplied skip_chars offset from the end
        skip_chars = max(0, total_len - skip_chars - max_chars)

    res_lines = []
    input_cursor = 0  # Current logical position in the "full" output (with line numbers)

    for i, line in enumerate(lines, start_line):
        line_with_num = f"{i}: {line}" if line_numbers else line
        # Length of the line in output format (including the trailing \n)
        line_len = len(line_with_num) + 1

        # 1. Skip the entire line if it falls entirely before skip_chars
        if input_cursor + line_len <= skip_chars:
            input_cursor += line_len
            continue

        # 2. If the line partially or fully falls within the visible window
        effective_line = line_with_num
        if input_cursor < skip_chars:
            # Offset within the first visible line
            offset = skip_chars - input_cursor
            effective_line = line_with_num[offset:]

        res_lines.append(effective_line)
        input_cursor += line_len  # Advance cursor by FULL line length

        # 3. Cumulative check against max_chars
        if max_chars is not None and max_chars > 0:
            current_combined = "\n".join(res_lines)
            if len(current_combined) >= max_chars:
                final_text = (
                    current_combined[:max_chars]
                    + f"\n... [Text truncated: limit {max_chars} characters exceeded]"
                )
                if skip_chars > 0:
                    final_text = (
                        f"[Text truncated: {skip_chars} characters skipped at the beginning]\n... "
                        + final_text
                    )
                return final_text

    final_combined = "\n".join(res_lines)
    if skip_chars > 0:
        final_combined = (
            f"[Text truncated: {skip_chars} characters skipped at the beginning]\n... "
            + final_combined
        )

    return final_combined


# --- BASE STRATEGIES ---
class ReadStrategy(ABC):
    @abstractmethod
    def read(self, path: str, **kwargs) -> str:
        pass

    @abstractmethod
    def validate(self, **kwargs):
        pass


class SaveStrategy(ABC):
    @abstractmethod
    def save(self, path: str, content: str, **kwargs) -> str:
        pass

    @abstractmethod
    def validate(self, content: str, **kwargs):
        pass

    @abstractmethod
    def transform(self, existing_content: str, new_content: str, **kwargs) -> str:
        """Applies a change to the content string and returns the result."""
        pass


# --- READ IMPLEMENTATIONS ---
class FullReadStrategy(ReadStrategy):
    def validate(self, **kwargs):
        pass

    def read(self, path: str, **kwargs) -> str:
        max_chars = kwargs.get("max_chars", 10000)
        skip_chars = kwargs.get("skip_chars", 0)
        line_numbers = kwargs.get("line_numbers", False)

        if (
            os.path.getsize(path) > 1024 * 1024
            and not skip_chars
            and not kwargs.get("force", False)
        ):
            raise ValueError("File too large (>1MB). Use pagination (skip_chars) or 'lines' mode.")

        with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
            text = f.read()

        return apply_read_filters(
            text, max_chars, skip_chars, line_numbers, direction=kwargs.get("direction", "begin")
        )


class SectionReadStrategy(ReadStrategy):
    def validate(self, **kwargs):
        if not kwargs.get("section_name"):
            raise ValueError("Mode 'section' (read) requires 'section_name'.")

    def read(self, path: str, **kwargs) -> str:
        self.validate(**kwargs)
        section_name = kwargs.get("section_name")

        with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
            content = f.read()

        section_text, start_pos, _ = extract_markdown_section(content, section_name)
        if section_text is None:
            raise ValueError(f"Section '{section_name}' not found in {os.path.basename(path)}.")

        # Determine the start line of the section relative to the beginning of the file
        start_line = content[:start_pos].count("\n") + 1
        return apply_read_filters(
            section_text,
            kwargs.get("max_chars", 10000),
            kwargs.get("skip_chars", 0),
            kwargs.get("line_numbers", False),
            start_line=start_line,
            direction=kwargs.get("direction", "begin"),
        )


class LinesReadStrategy(ReadStrategy):
    def validate(self, **kwargs):
        if "start_line" not in kwargs and "end_line" not in kwargs:
            raise ValueError("Mode 'lines' (read) requires 'start_line' or 'end_line'.")

    def read(self, path: str, **kwargs) -> str:
        self.validate(**kwargs)
        start_line = kwargs.get("start_line", 1)
        end_line = kwargs.get("end_line")

        lines = []
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
            for i, line in enumerate(f, 1):
                if i >= start_line:
                    lines.append(
                        line.rstrip("\n")
                    )  # strip trailing \n for correct apply_read_filters behaviour
                if end_line and i >= end_line:
                    break

        text = "\n".join(lines)
        return apply_read_filters(
            text,
            kwargs.get("max_chars", 10000),
            kwargs.get("skip_chars", 0),
            kwargs.get("line_numbers", False),
            start_line=start_line,
            direction=kwargs.get("direction", "begin"),
        )


# --- SAVE IMPLEMENTATIONS ---


class ReplaceFileStrategy(SaveStrategy):
    def validate(self, content: str, **kwargs):
        if not content.strip():
            raise ValueError("Mode 'replace_file' requires non-empty content.")

    def transform(self, existing_content: str, new_content: str, **kwargs) -> str:
        self.validate(new_content, **kwargs)
        return new_content

    def save(self, path: str, content: str, **kwargs) -> str:
        new_content = self.transform("", content, **kwargs)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(new_content)
        return f"Artifact {os.path.basename(path)} fully overwritten."


class AppendSectionStrategy(SaveStrategy):
    def validate(self, content: str, **kwargs):
        if not kwargs.get("section_name"):
            raise ValueError("Mode 'append_section' (write) requires 'section_name'.")
        if not content.strip():
            raise ValueError("Mode 'append_section' requires non-empty content.")

    def transform(self, existing_content: str, new_content: str, **kwargs) -> str:
        self.validate(new_content, **kwargs)
        section_name = kwargs.get("section_name")
        header_level = kwargs.get("header_level", 2)

        clean_name = clean_section_name(section_name)
        SectionNotExistsValidator(existing_content, clean_name, "in-memory-file").validate()

        new_content = strip_duplicated_header(new_content, clean_name)
        header = f"\n\n{'#' * header_level} {clean_name}\n"

        return existing_content.rstrip() + header + new_content + "\n"

    def save(self, path: str, content: str, **kwargs) -> str:
        existing_content = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
                existing_content = f.read()

        final_content = self.transform(existing_content, content, **kwargs)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(final_content)
        return (
            f"Section '{clean_section_name(kwargs.get('section_name'))}' appended to end of file."
        )


class ReplaceSectionStrategy(SaveStrategy):
    def validate(self, content: str, **kwargs):
        if not kwargs.get("section_name"):
            raise ValueError("Mode 'replace_section' (write) requires 'section_name'.")
        if not content.strip():
            raise ValueError("Mode 'replace_section' requires non-empty content.")

    def transform(self, existing_content: str, new_content: str, **kwargs) -> str:
        self.validate(new_content, **kwargs)
        section_name = kwargs.get("section_name")
        header_level = kwargs.get("header_level", 2)

        clean_name = clean_section_name(section_name)
        ranges = find_all_sections(existing_content, clean_name)
        if not ranges:
            raise ValueError(f"Section '{section_name}' not found.")
        if len(ranges) > 1:
            raise ValueError(f"Multiple sections named '{section_name}' found. Fix manually.")

        start, end = ranges[0]
        new_content = strip_duplicated_header(new_content, clean_name)
        header = f"\n\n{'#' * header_level} {clean_name}\n"

        return (
            existing_content[:start].rstrip()
            + header
            + new_content
            + "\n"
            + existing_content[end:].lstrip()
        )

    def save(self, path: str, content: str, **kwargs) -> str:
        with open(path, encoding="utf-8", errors="replace") as f:
            existing_content = f.read()

        final_content = self.transform(existing_content, content, **kwargs)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(final_content)
        return f"Section '{clean_section_name(kwargs.get('section_name'))}' successfully updated."


class ReplaceChunkStrategy(SaveStrategy):
    def validate(self, content: str, **kwargs):
        if "start_line" not in kwargs or "end_line" not in kwargs:
            raise ValueError("Mode 'replace_chunk' REQUIRES start_line and end_line (1-indexed).")

    def transform(self, existing_content: str, new_content: str, **kwargs) -> str:
        self.validate(new_content, **kwargs)
        start_line = kwargs.get("start_line")
        end_line = kwargs.get("end_line")
        effective_end = end_line if end_line is not None else start_line

        lines = existing_content.splitlines(keepends=True)
        if existing_content and not existing_content.endswith("\n"):
            if lines:
                lines[-1] += "\n"

        if start_line < 1 or start_line > len(lines) + 1:
            raise ValueError(f"Invalid start line: {start_line}. File has {len(lines)} lines.")

        pre = lines[: start_line - 1]
        post = lines[effective_end:]

        if new_content and not new_content.endswith("\n"):
            new_content += "\n"

        return "".join(pre) + new_content + "".join(post)

    def save(self, path: str, content: str, **kwargs) -> str:
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
            existing_content = f.read()

        final_content = self.transform(existing_content, content, **kwargs)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(final_content)
        return (
            f"Line range {kwargs.get('start_line')}-{kwargs.get('end_line')} successfully replaced."
        )


class PatchStrategy(SaveStrategy):
    def validate(self, content: str, **kwargs):
        if not kwargs.get("old_str"):
            raise ValueError("Mode 'patch' requires 'old_str'.")
        if not content.strip():
            raise ValueError("Mode 'patch' requires non-empty replacement content.")

    def transform(self, existing_content: str, new_content: str, **kwargs) -> str:
        self.validate(new_content, **kwargs)
        old_str = kwargs.get("old_str")

        count = existing_content.count(old_str)
        if count == 0:
            raise ValueError("Patch target string not found.")
        if count > 1:
            raise ValueError(f"Patch target string found {count} times. The match must be unique.")

        return existing_content.replace(old_str, new_content)

    def save(self, path: str, content: str, **kwargs) -> str:
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
            existing_content = f.read()

        final_content = self.transform(existing_content, content, **kwargs)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(final_content)

        return f"Artifact {os.path.basename(path)} successfully updated (patch applied)."


class DeleteSectionStrategy(SaveStrategy):
    def validate(self, content: str, **kwargs):
        if not kwargs.get("section_name"):
            raise ValueError("Mode 'delete_section' requires 'section_name'.")

    def transform(self, existing_content: str, new_content: str, **kwargs) -> str:
        self.validate(new_content, **kwargs)
        section_name = kwargs.get("section_name")
        clean_name = clean_section_name(section_name)
        ranges = find_all_sections(existing_content, clean_name)

        if not ranges:
            raise ValueError(f"Section '{section_name}' not found.")
        if len(ranges) > 1:
            raise ValueError(f"Multiple sections named '{section_name}' found. Delete manually.")

        start, end = ranges[0]
        return (
            existing_content[:start].rstrip() + "\n\n" + existing_content[end:].lstrip()
        ).strip() + "\n"

    def save(self, path: str, content: str, **kwargs) -> str:
        with open(path, encoding="utf-8", errors="replace") as f:
            existing_content = f.read()

        final_content = self.transform(existing_content, content, **kwargs)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(final_content)

        return f"Section '{clean_section_name(kwargs.get('section_name'))}' successfully deleted."


# --- FACTORY ---
class ArtifactStrategyFactory:
    _read_map = {
        "full": FullReadStrategy(),
        "section": SectionReadStrategy(),
        "lines": LinesReadStrategy(),
    }
    _save_map = {
        "replace_file": ReplaceFileStrategy(),
        "create": ReplaceFileStrategy(),
        "new": ReplaceFileStrategy(),
        "replace_section": ReplaceSectionStrategy(),
        "append_section": AppendSectionStrategy(),
        "replace_chunk": ReplaceChunkStrategy(),
        "patch": PatchStrategy(),
        "delete_section": DeleteSectionStrategy(),
    }

    @classmethod
    def get_read_strategy(cls, mode: str) -> ReadStrategy:
        strategy = cls._read_map.get(mode)
        if not strategy:
            raise ValueError(f"Unknown read mode: {mode}")
        return strategy

    @classmethod
    def get_save_strategy(cls, mode: str) -> SaveStrategy:
        strategy = cls._save_map.get(mode)
        if not strategy:
            raise ValueError(f"Unknown write mode: {mode}")
        return strategy
