import os
from dataclasses import dataclass
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from tools.utils.filesystem_utils import validate_artifact_path, validate_project_path


@dataclass
class BuildResult:
    success: bool
    output_path: str | None
    steps_run: int
    warnings: list[str]
    error: str | None = None

class OutputConfig(BaseModel):
    format: Literal["single_file", "directory"]
    filename: str | None = None
    dir_name: str | None = None

class SanitizeRule(BaseModel):
    """Content sanitization rule applied before build assembly."""
    regex: str | None = None
    replace: str = ""
    remove_section: str | None = None
    replace_text: str | None = None
    with_text: str | None = None
    preset: str | None = None

class StepConfig(BaseModel):
    action: str
    content: str | None = None
    path: str | None = None
    project: str | None = None  # Cross-project artifact source (None = current project)
    mode: str | None = None
    section_name: str | None = None
    filename: str | None = None
    sanitize: list[SanitizeRule] | None = None
    
    # Fields for validation and RegEx extraction
    regex: str | None = None
    expected: str | int | float | bool | None = None
    error_message: str | None = None
    skip_reference: bool | None = False
    use_findall: bool | None = False
    
    # Allows other fields gracefully
    model_config = {"extra": "allow"}

class VersionConfig(BaseModel):
    """Configuration for dynamic version extraction."""
    source: str
    regex: str

MANIFEST_SCHEMA_VERSION = 1

class BuildManifest(BaseModel):
    name: str
    version: str | VersionConfig
    schema_version: int = Field(default=1)
    output: OutputConfig
    steps: list[StepConfig]

def parse_manifest(project: str, build_name: str) -> BuildManifest:
    """Reads and validates the build manifest (Phase 1)."""
    prj_path = validate_project_path(project)
    builds_dir = os.path.join(prj_path, "builds")
    
    manifest_path = os.path.join(builds_dir, f"{build_name}.yaml")
    if not os.path.exists(manifest_path):
        manifest_path = os.path.join(builds_dir, f"{build_name}.yml")
        
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest '{build_name}' not found in {builds_dir}")
        
    with open(manifest_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
        
    if not data or not isinstance(data, dict):
        raise ValueError("Invalid YAML structure")
        
    try:
        manifest = BuildManifest(**data)
        
        # Phase 1.1: Resolve dynamic version
        if isinstance(manifest.version, VersionConfig):
            resolved_version = resolve_dynamic_version(project, manifest.version)
            manifest.version = resolved_version
            
        import logging
        logger = logging.getLogger("Builds")
        if manifest.schema_version != MANIFEST_SCHEMA_VERSION:
            logger.warning(f"Manifest '{build_name}' uses schema_version {manifest.schema_version}, but system expects {MANIFEST_SCHEMA_VERSION}. Backward compatibility is active.")
            
        return manifest
    except ValidationError as e:
        raise ValueError(f"Manifest schema validation failed: {e}")

def resolve_dynamic_version(project: str, config: VersionConfig) -> str:
    """Extracts the version from a specified file using a regular expression."""
    import re
    
    # Validate the source file path (may be an artifact or any file inside the project)
    # Try as an artifact first
    try:
        source_path = validate_artifact_path(project, config.source)
    except Exception:
        # If not an artifact, resolve relative to the project root
        prj_path = validate_project_path(project)
        source_path = os.path.join(prj_path, config.source)
        
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source file for versioning not found: {source_path}")
        
    with open(source_path, encoding="utf-8") as f:
        content = f.read()
        
    match = re.search(config.regex, content)
    if not match:
        raise ValueError(f"Version regex '{config.regex}' not matched in file '{config.source}'")
        
    # Return the first capture group, or the full match if no groups
    return match.group(1) if match.groups() else match.group(0)

def prepare_release_directory(project: str, manifest: BuildManifest, context) -> str:
    """Prepares the release directory (Phase 2). Returns the path to the generated directory."""
    prj_path = validate_project_path(project)
    output_base_dir = os.path.join(prj_path, ".output")
    
    # Release dir name: custom dir_name or default {name}/{version}
    # Supports {name} and {version} placeholders
    raw_dir_name = manifest.output.dir_name or f"{manifest.name}/{{{{VERSION}}}}"
    # Simple placeholder replacement (legacy support)
    release_dir_name = raw_dir_name.replace("{version}", str(manifest.version)).replace("{name}", manifest.name)
    from tools.utils.template_renderer import TemplateRenderer
    release_dir_name = TemplateRenderer.render(release_dir_name, context)
    
    release_dir_path = os.path.normpath(os.path.join(output_base_dir, release_dir_name))
    
    # Clear output dir so each build is idempotent and clean
    if os.path.exists(release_dir_path):
        import shutil
        shutil.rmtree(release_dir_path)
        
    os.makedirs(release_dir_path, exist_ok=True)
    return release_dir_path

def run_project_build_logic(project: str, build_name: str, verbose: bool = False, variables: dict[str, str] | None = None) -> BuildResult:
    """
    Executes a build based on a YAML manifest.
    Integrates Phases 1, 2, 3, and 4. Writes an exception log on failure.
    """
    import traceback
    
    try:
        # Phase 1
        manifest = parse_manifest(project, build_name)
    
        # Define base output folder
        prj_path = validate_project_path(project)
        output_base_dir = os.path.join(prj_path, ".output")
    
    
        # Build context up front so it can be used for path rendering
        from tools.build_processors import BuildContext, ProcessorFactory
        context = BuildContext(project, manifest, "", verbose=verbose, variables=variables)
        
        # Phase 2
        release_dir = prepare_release_directory(project, manifest, context)
        context.release_dir = release_dir  # Update path
        
        # Phase 3: Execute Payload Steps
        for step in manifest.steps:
            processor = ProcessorFactory.get_processor(step.action)
            processor.process(step, context)
            
        # Phase 4: Compile output
        if manifest.output.format == "single_file":
            # If no filename supplied, generate a default one
            raw_filename = manifest.output.filename or f"{manifest.name}_v{{{{VERSION}}}}.md"
            # Replace placeholders
            filename = raw_filename.replace("{version}", str(manifest.version)).replace("{name}", manifest.name)
            from tools.utils.template_renderer import TemplateRenderer
            filename = TemplateRenderer.render(filename, context)
            
            output_path = os.path.join(release_dir, filename)
            # Auto-create subdirectories if filename contains a path
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(context.output_buffer))
                
        # For directory mode, files are already saved by individual processors (Phase 3)
        res_rel_path = os.path.relpath(release_dir, output_base_dir)
        return BuildResult(
            success=True,
            output_path=f".output/{res_rel_path}/",
            steps_run=len(manifest.steps),
            warnings=[]
        )
        
    except Exception as e:
        error_msg = f"Build error for '{build_name}': {str(e)}"
        trace = traceback.format_exc()
        
        # Save detailed error log next to the manifest
        try:
            prj_path = validate_project_path(project)
            log_dir = os.path.join(prj_path, "builds")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, f"{build_name}_error.log")
            
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(error_msg + "\n\n" + trace)
                
            error_msg += f"\n(Detailed traceback saved in {log_path})"
        except Exception as log_err:
            error_msg += f"\n(Failed to save log: {log_err})"
            
        return BuildResult(
            success=False,
            output_path=None,
            steps_run=0,
            warnings=[],
            error=error_msg
        )

