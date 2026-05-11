from typing import Any

from tools.artifact_pipeline import save_project_artifacts_logic as execute_pipeline


async def save_project_artifacts_logic(
    project: str, updates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Manages artifact loading/modification via the main pipeline.
    Effectively acts as a facade to PipelineContext.
    """
    return await execute_pipeline(project, updates)
