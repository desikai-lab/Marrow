import os
import re
import shutil
from abc import ABC, abstractmethod

# TODO: move to utils.
# In the future, direct artifact calls may be extracted into a dedicated sandbox.
from tools.artifacts import get_project_artifact_outline_logic, read_artifact_logic
from tools.builds import BuildManifest, SanitizeRule, StepConfig
from tools.utils.cleaner_presets import PRESETS
from tools.utils.filesystem_utils import validate_artifact_path, validate_project_path
from tools.utils.markdown_utils import extract_markdown_section


class BuildContext:
    def __init__(self, project: str, manifest: BuildManifest, release_dir: str, verbose: bool = False, variables: dict[str, str] | None = None):
        import datetime
        self.project = project
        self.manifest = manifest
        self.release_dir = release_dir
        self.output_buffer: list[str] = []
        self.verbose = verbose

        resolved: dict[str, str] = {}
        if manifest.version is not None:
            v = manifest.version
            if isinstance(v, str):
                resolved["VERSION"] = v

        resolved["PROJECT_NAME"] = project
        resolved["BUILD_NAME"] = manifest.name
        resolved["DATE"] = datetime.date.today().strftime("%Y-%m-%d")

        if variables:
            resolved.update({k.upper(): v for k, v in variables.items()})

        self.variables = resolved

from tools.utils.markdown_fence import build_fenced_ranges, in_fenced_range  # noqa: E402
from tools.utils.template_renderer import TemplateRenderer  # noqa: E402


def _extract_section_for_regex(content: str, section_header: str) -> str:
    """
    Extracts a Markdown section by header, correctly ignoring headings
    inside fenced code blocks when searching for the section boundary.
    Uses the shared markdown_fence utility for fence-awareness.
    """
    clean_header = section_header.lstrip("#").strip()
    header_regex = re.escape(clean_header).replace(r"\ ", r"\s+").replace(r" ", r"\s+")
    header_pattern = re.compile(rf"^(#+)\s*{header_regex}\s*$", re.MULTILINE | re.IGNORECASE)

    match = header_pattern.search(content)
    if not match:
        return ""

    level = len(match.group(1))
    start_pos = match.start()

    fenced_ranges = build_fenced_ranges(content)

    # Search for the next real header at the same or higher level, outside any code block
    next_header_pattern = re.compile(rf"^#{{1,{level}}}\s+", re.MULTILINE)
    end_pos = len(content)
    for m in next_header_pattern.finditer(content, match.end()):
        if not in_fenced_range(m.start(), fenced_ranges):
            end_pos = m.start()
            break

    return content[start_pos:end_pos].strip("\n")

def apply_filters(content: str, rules: list[SanitizeRule] | None) -> str:
    """Applies sanitization rules to content sequentially."""
    if not rules:
        return content
        
    result = content
    for rule in rules:
        # 1. Apply presets
        if rule.preset and rule.preset in PRESETS:
            pattern = PRESETS[rule.preset]
            result = re.sub(pattern, rule.replace, result, flags=re.MULTILINE | re.DOTALL)
            
        # 2. Regular expression rules
        if rule.regex:
            result = re.sub(rule.regex, rule.replace, result, flags=re.MULTILINE | re.DOTALL)
            
        # 3. Plain text replacement
        if rule.replace_text:
            new_text = rule.with_text if rule.with_text is not None else ""
            result = result.replace(rule.replace_text, new_text)
            
        # 4. Markdown section removal
        if rule.remove_section:
            _, start, end = extract_markdown_section(result, rule.remove_section)
            if start is not None and end is not None:
                # Excise the section
                result = result[:start] + result[end:]
                
    return result

class ProcessorFactory:
    _registry: dict[str, type['StepProcessor']] = {}

    @classmethod
    def register(cls, action: str):
        def wrapper(processor_cls: type['StepProcessor']):
            cls._registry[action] = processor_cls
            return processor_cls
        return wrapper

    @classmethod
    def get_processor(cls, action: str) -> 'StepProcessor':
        if action not in cls._registry:
            raise ValueError(f"Unknown pipeline action: '{action}'")
        return cls._registry[action]()

class StepProcessor(ABC):
    @abstractmethod
    def process(self, step: StepConfig, context: BuildContext):
        """Processes a pipeline step."""
        pass

@ProcessorFactory.register('append_text')
class AppendTextProcessor(StepProcessor):
    def process(self, step: StepConfig, context: BuildContext):
        content = apply_filters(step.content or "", step.sanitize)
        content = TemplateRenderer.render(content, context)
        if context.manifest.output.format == "single_file":
            context.output_buffer.append(content)
        elif context.manifest.output.format == "directory":
            filename = step.filename or "appended_text.md"
            dest_path = os.path.join(context.release_dir, filename)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "a", encoding="utf-8") as f:
                f.write(content + "\n")

@ProcessorFactory.register('include_artifact')
class IncludeArtifactProcessor(StepProcessor):
    def process(self, step: StepConfig, context: BuildContext):
        if not step.path:
            raise ValueError("Action 'include_artifact' requires 'path'")
            
        mode = step.mode or "full"
        source_project = step.project or context.project
        
        if mode == "outline_only":
            content = get_project_artifact_outline_logic(source_project, step.path)
        elif mode == "regex":
            if not step.regex:
                raise ValueError("Mode 'regex' requires 'regex' pattern")
                
            # Read the full file, then extract the section using the local fence-aware helper.
            # extract_markdown_section from markdown_utils is intentionally NOT used here:
            # it cannot skip headings inside fenced code blocks,
            # which leads to premature section truncation.
            full_content = read_artifact_logic(
                project=source_project,
                rel_path=step.path,
                mode="full",
                section_name=None,
                max_chars=0, force=True
            )
            if step.section_name:
                full_content = _extract_section_for_regex(full_content, step.section_name)
            
            # Apply regex search
            match = re.search(step.regex, full_content, re.MULTILINE | re.DOTALL)
            if not match:
                content = ""  # Not found — empty (acts as a filter for missing optional sections)
            else:
                # Extract capture group or full match
                content = match.group(1) if match.groups() else match.group(0)
        else:
            content = read_artifact_logic(
                project=source_project,
                rel_path=step.path,
                mode=mode,
                section_name=step.section_name,
                max_chars=0,   # Disable limit for build assembly
                force=True     # Skip 1 MB size check
            )
            
        # Apply sanitization filters
        content = apply_filters(content, step.sanitize)
        content = TemplateRenderer.render(content, context)
            
        if context.manifest.output.format == "single_file":
            if step.skip_reference:
                # Insert as-is without separators
                context.output_buffer.append(content)
            else:
                 separator = f"\n\n--- Artifact: {step.path} ---\n\n"
                 context.output_buffer.append(f"{separator}{content}")
        elif context.manifest.output.format == "directory":
            dest_file = step.filename or os.path.basename(step.path)
            dest_path = os.path.join(context.release_dir, dest_file)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(content)

@ProcessorFactory.register('copy_file')
class CopyFileProcessor(StepProcessor):
    def process(self, step: StepConfig, context: BuildContext):
        if not step.path:
            raise ValueError("Action 'copy_file' requires 'path'")
            
        if context.manifest.output.format == "single_file":
            # Ignored for single_file mode by design
            pass
        elif context.manifest.output.format == "directory":
            src_path = validate_artifact_path(context.project, step.path)
            dest_file = step.filename or step.path
            dest_path = os.path.join(context.release_dir, dest_file)
            
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(src_path, dest_path)

class Specification(ABC):
    @abstractmethod
    def is_satisfied_by(self, content: str) -> bool: ...
    @abstractmethod
    def error_message(self) -> str: ...

class RegexMatchSpec(Specification):
    def __init__(self, regex: str, expected: str, step_path: str, custom_error: str | None = None):
        self.regex = regex
        self.expected = str(expected).strip()
        self.step_path = step_path
        self.custom_error = custom_error
        self.actual = ""
        self._error = ""

    def is_satisfied_by(self, content: str) -> bool:
        match = re.search(self.regex, content, re.MULTILINE | re.DOTALL)
        if not match:
            self._error = self.custom_error or f"Validation failed: Entry for regex '{self.regex}' not found in {self.step_path}"
            return False
        
        actual = match.group(1) if match.groups() else match.group(0)
        self.actual = str(actual).strip()
        if self.actual != self.expected:
            self._error = self.custom_error or f"Validation failed for {self.step_path}. Expected '{self.expected}', but got '{self.actual}'"
            return False
        return True
        
    def error_message(self) -> str:
        return self._error

class RegexFindallSpec(Specification):
    def __init__(self, regex: str, expected: str, step_path: str, custom_error: str | None = None):
        self.regex = regex
        self.expected = str(expected).strip()
        self.step_path = step_path
        self.custom_error = custom_error
        self.actual = ""
        self._error = ""

    def is_satisfied_by(self, content: str) -> bool:
        matches = re.findall(self.regex, content, re.MULTILINE | re.DOTALL)
        if not matches:
            self._error = self.custom_error or f"Validation failed: No matches for regex '{self.regex}' in {self.step_path}"
            return False
        
        actual = "".join([m if isinstance(m, str) else "".join(m) for m in matches])
        self.actual = str(actual).strip()
        if self.actual != self.expected:
            self._error = self.custom_error or f"Validation failed for {self.step_path}. Expected '{self.expected}', but got '{self.actual}'"
            return False
        return True
        
    def error_message(self) -> str:
        return self._error

@ProcessorFactory.register('validate')
class ValidateProcessor(StepProcessor):
    """
    Checks a file for a specific value using a RegEx.
    Aborts the build with an error if the value does not match expected.
    """
    def process(self, step: StepConfig, context: BuildContext):
        if not step.path or not step.regex or step.expected is None:
            raise ValueError("Action 'validate' requires 'path', 'regex', and 'expected'")
            
        try:
            full_path = validate_artifact_path(context.project, step.path)
        except Exception:
            prj_path = validate_project_path(context.project)
            full_path = os.path.join(prj_path, step.path)
            
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Validation source file not found: {step.path}")
            
        with open(full_path, encoding="utf-8") as f:
            content = f.read()
            
        if step.section_name:
            content, _, _ = extract_markdown_section(content, step.section_name)
            if not content:
                raise ValueError(step.error_message or f"Validation failed: Section '{step.section_name}' not found in {step.path}")
            
        spec = RegexFindallSpec(step.regex, step.expected, step.path, step.error_message) if step.use_findall else RegexMatchSpec(step.regex, step.expected, step.path, step.error_message)
        
        if not spec.is_satisfied_by(content):
            if context.verbose:
                print(f"[VERBOSE] Validation for {step.path}:\n  Regex: {step.regex}\n  Expected: '{step.expected}'\n  Actual: '{spec.actual}'")
            raise ValueError(spec.error_message())
            
        print(f"Validation successful for {step.path}: '{spec.actual.strip()}'")

@ProcessorFactory.register('hygiene_check')
class HygieneCheckProcessor(StepProcessor):
    """ADR-15 extension: checks builds/ for stale {manifest_name}_error.log files."""

    def process(self, step: StepConfig, context: BuildContext):
        project_root = validate_project_path(context.project)
        scan_dir = os.path.join(project_root, "builds")
        target = f"{context.manifest.name}_error.log"
        log_path = os.path.join(scan_dir, target)

        severity = getattr(step, "severity", None) or step.model_extra.get("severity", "warn")

        if os.path.exists(log_path):
            msg = f"[HYGIENE] Stale error log found: builds/{target}. Remove it before next run."
            if severity == "error":
                raise RuntimeError(msg)
            context.output_buffer.append(f"\n⚠️  {msg}")
        else:
            context.output_buffer.append(f"\n✅ [HYGIENE] No stale error log (builds/{target}).")



