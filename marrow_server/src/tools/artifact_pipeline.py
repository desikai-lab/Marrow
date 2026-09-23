import asyncio
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

from common.project_path import ProjectPath

# legacy reference removed
from config import VECT_DEBOUNCE_SECONDS

from tools.pipeline_base import PersistPipeline
from tools.utils.artifact_integrity_hooks import ArtifactIntegrityRegistry
from tools.utils.artifact_strategies import (
    ArtifactStrategyFactory,
    find_unknown_fields,
)
from tools.utils.cleaner import ContentCleaner
from tools.utils.filesystem_utils import (
    create_artifact_backup,
    resolve_artifact_project_path,
    validate_artifact_path,
    validate_project_path,
)
from tools.utils.project_settings import ProjectSettings, load_project_settings

if TYPE_CHECKING:
    from storage.repositories import ArtifactChunkRepository

logger = logging.getLogger("marrow.pipeline")


async def maybe_extract_keywords(
    settings: ProjectSettings,
    chunk_repo: "ArtifactChunkRepository",
    path: str,
    chunks: list,
    updated_at: str,
) -> None:
    """Application-level step: if LITERAL_EXTRACTION is on for the project,
    extracts keywords from already-chunked units and persists them via
    ArtifactChunkRepository.save_keyword_records.
    `settings` is resolved once by the caller (VectorizationHandler.handle,
    reindex-chunks CLI) -- this helper never loads settings itself.
    The caller also passes its ArtifactChunkRepository (`uow.chunks` in the
    handler, `repo` in the CLI), so the helper needs no project_root.
    ArtifactChunkRepository itself never sees raw chunks for this purpose.
    Isolated failure: never raises -- the chunk upsert this follows has
    already succeeded and is not rolled back by a keyword extraction error.
    """
    if not settings.literal_extraction or not chunks:
        return
    try:
        from storage.entities import ArtifactChunkKeywordRecord
        from storage.keyword_extractor import ExtractiveKeywordExtractor

        results = ExtractiveKeywordExtractor().extract_detailed(chunks)
        records = [
            ArtifactChunkKeywordRecord(
                path=path,
                start_line=c.start_line,
                end_line=c.end_line,
                keywords=" ".join(r.kept),
                extracted_at=updated_at,
            )
            for c, r in zip(chunks, results)
        ]
        await chunk_repo.save_keyword_records(path, records)
    except Exception as exc:
        logger.warning(
            "Keyword extraction failed for %s: %s (chunk indexing unaffected)", path, exc
        )


class DefaultPipeline(PersistPipeline):
    """Today's generic artifact-write flow, extracted out of PersistHandler.handle's
    per-path loop body and split into named steps -- the same decomposition style
    SessionPipeline.run uses (Task 2). ValidationHandler and GroupingHandler still
    run upstream of this, unchanged. Has no file-specific knowledge: it does not
    know session.md exists. `run()` is a short orchestrator only."""

    async def run(self, ctx, path: str, group: list[tuple]) -> None:
        try:
            project_path = resolve_artifact_project_path(ctx.project, path)
            current_content = await self._read_old_content(ctx.project, project_path)
            final_content, applied_successfully = await self._apply_updates(
                ctx, project_path, group, current_content
            )
            if applied_successfully:
                # Backup moves here: right before the write we're now committed
                # to, gated on applied_successfully being non-empty (Finding #8).
                await asyncio.to_thread(create_artifact_backup, ctx.project, project_path)
                await self._save_content(project_path, final_content)
                for idx in applied_successfully:
                    ctx.results[idx]["message"] += " File saved."
        except Exception as e:
            for original_idx, _ in group:
                if (
                    not ctx.results[original_idx]
                    or ctx.results[original_idx].get("status") != "error"
                ):
                    ctx.results[original_idx] = {
                        "path": path,
                        "status": "error",
                        "message": f"File save failed: {str(e)}",
                    }

    async def _read_old_content(self, project: str, project_path: ProjectPath) -> str:
        """Read the live on-disk content once (empty string if the file doesn't
        exist yet). No side effect here -- the backup moves to run(), gated on a
        genuine, validated intent to overwrite (Finding #8)."""
        if not await project_path.exists_async():
            return ""
        return await project_path.read_async()

    async def _apply_updates(
        self, ctx, project_path: ProjectPath, group: list[tuple], current_content: str
    ) -> tuple[str, list[int]]:
        """Apply every update in the group in-memory, in GroupingHandler's existing
        order, running the per-path ArtifactIntegrityRegistry hook (e.g.
        HistoryMdIntegrityHook for sessions/history.md) before each transform."""
        applied_successfully: list[int] = []
        rel_path = project_path.relative_path
        for original_idx, update in group:
            try:
                mode = update["mode"]
                strategy = ArtifactStrategyFactory.get_save_strategy(mode)
                params = update.copy()
                explicit_fields = params.pop("_explicit_fields", None)
                if explicit_fields is None:
                    explicit_fields = set(params.keys())
                new_val = params.pop("content", "")

                hook = ArtifactIntegrityRegistry.get_hook(rel_path)
                if hook:
                    hook_params = {k: v for k, v in params.items() if k != "mode"}
                    new_val = await hook.validate_and_repair(
                        ctx.project, rel_path, new_val, mode, **hook_params
                    )

                current_content = strategy.transform(current_content, new_val, **params)
                warning = find_unknown_fields(strategy, explicit_fields)
                result_entry: dict[str, Any] = {
                    "path": rel_path,
                    "status": "success",
                    "message": f"Applied {mode} to memory successfully.",
                }
                if warning is not None:
                    result_entry["warning"] = warning
                ctx.results[original_idx] = result_entry
                applied_successfully.append(original_idx)
            except Exception as e:
                ctx.results[original_idx] = {"path": rel_path, "status": "error", "message": str(e)}
        return current_content, applied_successfully

    async def _save_content(self, project_path: ProjectPath, content: str) -> None:
        """The actual write. Raises on failure -- run()'s broad except then marks
        every update in the group as errored, matching today's behavior exactly."""
        await project_path.write_async(content)


class PipelineContext:
    def __init__(self, project: str, updates: list[dict[str, Any]]):
        self.project = project
        self.project_root = validate_project_path(project)
        self.updates = updates
        self.results = [None] * len(updates)
        self.grouped_updates = {}  # path -> list of (original_index, update_dict)


class BaseHandler:
    def __init__(self, next_handler=None):
        self.next_handler = next_handler

    async def handle(self, ctx: PipelineContext):
        if self.next_handler:
            return await self.next_handler.handle(ctx)


class ValidationHandler(BaseHandler):
    async def handle(self, ctx: PipelineContext):
        for i, update in enumerate(ctx.updates):
            path = update.get("path")
            mode = update.get("mode")
            if not path or not mode:
                ctx.results[i] = {
                    "path": path,
                    "status": "error",
                    "message": "Missing 'path' or 'mode'",
                }
                continue

            try:
                # Domain protection for architectural decision records
                if path == "memory/decisions.md" and mode != "append_section":
                    raise ValueError(
                        f"Domain protection: {mode} on memory/decisions.md is forbidden. ONLY append_section is permitted."
                    )

                # Minimal path validation
                if not validate_artifact_path(ctx.project, path):
                    raise ValueError(f"Invalid artifact path: {path}")
                # Validate that a strategy exists for this mode
                ArtifactStrategyFactory.get_save_strategy(mode)
            except Exception as e:
                ctx.results[i] = {"path": path, "status": "error", "message": str(e)}

        return await super().handle(ctx)


class GroupingHandler(BaseHandler):
    async def handle(self, ctx: PipelineContext):
        for i, update in enumerate(ctx.updates):
            if ctx.results[i] is not None:
                continue  # Skip already failed

            path = update["path"]
            if path not in ctx.grouped_updates:
                ctx.grouped_updates[path] = []
            ctx.grouped_updates[path].append((i, update))

        # Sorting within each group (ADR-06 / Task 5)
        for path, group in ctx.grouped_updates.items():
            # Rule: replace_chunk operations always come FIRST.
            # Within replace_chunk: descending by start_line.
            # (mode != "replace_chunk") yields False for chunks and True for others. False < True.
            group.sort(
                key=lambda x: (x[1].get("mode") != "replace_chunk", -x[1].get("start_line", 0))
            )

        return await super().handle(ctx)


class PersistHandler(BaseHandler):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        from tools.pipeline_dispatcher import PipelineDispatcher

        self._dispatcher = PipelineDispatcher()

    async def handle(self, ctx: PipelineContext):
        for path, group in ctx.grouped_updates.items():
            pipeline = self._dispatcher.get_pipeline(path)
            await pipeline.run(ctx, path, group)
        return await super().handle(ctx)


class VectorizationHandler(BaseHandler):
    async def handle(self, ctx: PipelineContext):
        settings = load_project_settings(
            ctx.project
        )  # F4000249: resolved once per handle(), not per path
        # Collect unique paths that were successfully modified
        success_paths = set()
        for res in ctx.results:
            if res and res.get("status") == "success":
                success_paths.add(res["path"])

        for path in success_paths:
            try:
                project_path = resolve_artifact_project_path(ctx.project, path)
                if not await project_path.exists_async():
                    continue

                content = await project_path.read_async()

                # Cleanup (ChangeLog, comments)
                cleaned = ContentCleaner.clean(content)

                # Vectorize and persist to index
                updated_at = datetime.now().isoformat()
                from storage.uow import UnitOfWork

                uow = UnitOfWork(ctx.project_root)
                await uow.artifacts.upsert(path, cleaned, updated_at)

                # Chunk the artifact and persist sections
                chunks = []
                try:
                    ext = os.path.splitext(path)[1].lower()
                    chunks = await uow.chunks.upsert_chunks(
                        path, cleaned, updated_at, ext=ext
                    )  # CHANGED: captures return
                except Exception as chunk_e:
                    logger.error(f"Failed to chunk artifact {path}: {chunk_e}")

                # F4000249: Stage 1 keyword lane -- application-level, flag-gated
                await maybe_extract_keywords(settings, uow.chunks, path, chunks, updated_at)

                # Debounce (configurable delay)
                if VECT_DEBOUNCE_SECONDS > 0:
                    await asyncio.sleep(VECT_DEBOUNCE_SECONDS)

            except Exception as e:
                logger.error(f"Failed to vectorize artifact {path}: {e}")

        return await super().handle(ctx)


async def save_project_artifacts_logic(
    project: str, updates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Batch artifact processing pipeline (Phase 3)."""
    ctx = PipelineContext(project, updates)

    # Chain: Validation -> Grouping -> Persist -> Vectorization
    pipeline = ValidationHandler(GroupingHandler(PersistHandler(VectorizationHandler())))

    await pipeline.handle(ctx)

    # Fallback fill for any unset results
    for i in range(len(ctx.results)):
        if ctx.results[i] is None:
            ctx.results[i] = {"status": "error", "message": "Unknown error in pipeline"}

    return ctx.results
