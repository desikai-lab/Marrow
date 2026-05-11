import os
import logging
import asyncio
import time
from typing import List, Dict, Any, Tuple
from datetime import datetime
from tools.utils.filesystem_utils import validate_artifact_path, validate_project_path, create_artifact_backup
from tools.utils.artifact_strategies import ArtifactStrategyFactory
from tools.utils.cleaner import ContentCleaner
# legacy reference removed
from config import VECT_DEBOUNCE_SECONDS

logger = logging.getLogger("marrow.pipeline")

class PipelineContext:
    def __init__(self, project: str, updates: List[Dict[str, Any]]):
        self.project = project
        self.project_root = validate_project_path(project)
        self.updates = updates
        self.results = [None] * len(updates)
        self.grouped_updates = {} # path -> list of (original_index, update_dict)

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
                ctx.results[i] = {"path": path, "status": "error", "message": "Missing 'path' or 'mode'"}
                continue
            
            try:
                # Domain protection for architectural decision records
                if path == "memory/decisions.md" and mode != "append_section":
                    raise ValueError(f"Domain protection: {mode} on memory/decisions.md is forbidden. ONLY append_section is permitted.")
                    
                # Minimal path validation
                validate_artifact_path(ctx.project, path)
                # Validate that a strategy exists for this mode
                ArtifactStrategyFactory.get_save_strategy(mode)
            except Exception as e:
                ctx.results[i] = {"path": path, "status": "error", "message": str(e)}

        return await super().handle(ctx)

class GroupingHandler(BaseHandler):
    async def handle(self, ctx: PipelineContext):
        for i, update in enumerate(ctx.updates):
            if ctx.results[i] is not None:
                continue # Skip already failed
            
            path = update["path"]
            if path not in ctx.grouped_updates:
                ctx.grouped_updates[path] = []
            ctx.grouped_updates[path].append((i, update))

        # Sorting within each group (ADR-06 / Task 5)
        for path, group in ctx.grouped_updates.items():
            # Rule: replace_chunk operations always come FIRST.
            # Within replace_chunk: descending by start_line.
            # (mode != "replace_chunk") yields False for chunks and True for others. False < True.
            group.sort(key=lambda x: (x[1].get("mode") != "replace_chunk", -x[1].get("start_line", 0)))
            
        return await super().handle(ctx)

class PersistHandler(BaseHandler):
    async def handle(self, ctx: PipelineContext):
        for path, group in ctx.grouped_updates.items():
            try:
                abs_path = validate_artifact_path(ctx.project, path)
                
                # Read file once
                current_content = ""
                file_exists = os.path.exists(abs_path)
                if file_exists:
                    def read_file():
                        with open(abs_path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
                            return f.read()
                    current_content = await asyncio.to_thread(read_file)
                
                # Backup once per file (only if the file already existed)
                if file_exists:
                    await asyncio.to_thread(create_artifact_backup, ctx.project, path)
                
                applied_successfully = []
                
                # Apply all updates in the group to the in-memory content
                for original_idx, update in group:
                    try:
                        mode = update["mode"]
                        strategy = ArtifactStrategyFactory.get_save_strategy(mode)
                        
                        # Avoid duplicating 'content' in **kwargs
                        params = update.copy()
                        new_val = params.pop("content", "")

                        # Apply transformation to the entire content
                        current_content = strategy.transform(
                            current_content, 
                            new_val, 
                            **params
                        )
                        
                        ctx.results[original_idx] = {
                            "path": path, 
                            "status": "success", 
                            "message": f"Applied {mode} to memory successfully."
                        }
                        applied_successfully.append(original_idx)
                    except Exception as e:
                        ctx.results[original_idx] = {
                            "path": path, 
                            "status": "error", 
                            "message": str(e)
                        }
                
                # Write final result ONCE, but only if any updates succeeded
                if applied_successfully:
                    def write_file(content):
                        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                        with open(abs_path, "w", encoding="utf-8-sig", newline="") as f:
                            f.write(content)
                    await asyncio.to_thread(write_file, current_content)
                    
                    # Update message for successful operations
                    for idx in applied_successfully:
                        ctx.results[idx]["message"] += " File saved."
                    
            except Exception as e:
                # Global file error (e.g. Permission Denied)
                for original_idx, _ in group:
                    # If not already marked as error, mark it now
                    if not ctx.results[original_idx] or ctx.results[original_idx].get("status") != "error":
                        ctx.results[original_idx] = {"path": path, "status": "error", "message": f"File save failed: {str(e)}"}

        return await super().handle(ctx)

class VectorizationHandler(BaseHandler):
    async def handle(self, ctx: PipelineContext):
        # Collect unique paths that were successfully modified
        success_paths = set()
        for res in ctx.results:
            if res and res.get("status") == "success":
                success_paths.add(res["path"])
        
        for path in success_paths:
            try:
                abs_path = validate_artifact_path(ctx.project, path)
                if not os.path.exists(abs_path): continue
                
                def read_file():
                    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                        return f.read()
                content = await asyncio.to_thread(read_file)
                
                # Cleanup (ChangeLog, comments)
                cleaned = ContentCleaner.clean(content)
                
                # Vectorize and persist to index
                updated_at = datetime.now().isoformat()
                from storage.uow import UnitOfWork
                uow = UnitOfWork(ctx.project_root)
                await uow.artifacts.upsert(path, cleaned, updated_at)
                
                # Chunk the artifact and persist sections
                try:
                    ext = os.path.splitext(path)[1].lower()
                    await uow.chunks.upsert_chunks(path, cleaned, updated_at, ext=ext)
                except Exception as chunk_e:
                    logger.error(f"Failed to chunk artifact {path}: {chunk_e}")
                
                # Debounce (configurable delay)
                if VECT_DEBOUNCE_SECONDS > 0:
                    await asyncio.sleep(VECT_DEBOUNCE_SECONDS)
                    
            except Exception as e:
                logger.error(f"Failed to vectorize artifact {path}: {e}")

        return await super().handle(ctx)

async def save_project_artifacts_logic(project: str, updates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Batch artifact processing pipeline (Phase 3)."""
    ctx = PipelineContext(project, updates)
    
    # Chain: Validation -> Grouping -> Persist -> Vectorization
    pipeline = ValidationHandler(
        GroupingHandler(
            PersistHandler(
                VectorizationHandler()
            )
        )
    )
    
    await pipeline.handle(ctx)
    
    # Fallback fill for any unset results
    for i in range(len(ctx.results)):
        if ctx.results[i] is None:
            ctx.results[i] = {"status": "error", "message": "Unknown error in pipeline"}
            
    return ctx.results
