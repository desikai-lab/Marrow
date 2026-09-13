from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.artifact_pipeline import PipelineContext


class PersistPipeline(ABC):
    """Common interface for the two path-routed persist pipelines (ADR-0047).

    `PersistHandler` only ever calls `run` through this interface -- it holds
    no knowledge of which concrete pipeline (`DefaultPipeline`, `SessionPipeline`)
    it is talking to. New file-specific pipelines, if ever needed, only have to
    implement this one method and be registered in `PipelineDispatcher`.
    """

    @abstractmethod
    async def run(self, ctx: "PipelineContext", path: str, group: list[tuple[int, dict]]) -> None:
        """Apply every update in `group` (all targeting `path`) and mutate
        `ctx.results` in place for each `(original_idx, update)` pair."""
        raise NotImplementedError
