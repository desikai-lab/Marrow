import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Resolve monorepo root (3 levels up: services → src → marrow_server → root)
_MONOREPO_ROOT = str(Path(__file__).parents[3])
if _MONOREPO_ROOT not in sys.path:
    sys.path.insert(0, _MONOREPO_ROOT)

from marrow_common.skeleton_schema import SkeletonChunk  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from config import PROJECTS_ROOT  # noqa: E402
from storage.entities import SkeletonChunkRecord  # noqa: E402
from storage.repositories.skeleton_repository import SkeletonRepository  # noqa: E402

logger = logging.getLogger("marrow.skeleton_command_service")


class SkeletonCommandService:
    """
    Orchestrates ingestion of pre-vectorized code skeleton payloads arriving
    from marrow_worker via POST /api/vectorize.

    Responsibilities:
      - Resolve (and optionally auto-create) the project root directory.
      - Map the Pydantic request payload to SkeletonChunkRecord DTOs.
      - Delegate persistence to SkeletonRepository.
    """

    async def ingest(self, payload, **kwargs) -> int:
        """
        Persists all chunks from the given VectorizeRequest payload.
        Returns the number of chunks stored.
        """
        # Validate incoming chunks against shared contract before ingesting (TD4000076)
        valid_chunks = []
        for chunk in payload.chunks:
            try:
                # Use model_dump if it's a Pydantic model, else use raw dict
                data = chunk.model_dump() if hasattr(chunk, "model_dump") else chunk
                # Ensure path and project are present for SkeletonChunk validation
                if isinstance(data, dict):
                    data.update({"path": payload.path, "project": payload.project_name})
                SkeletonChunk(**data)
                valid_chunks.append(chunk)
            except ValidationError as ve:
                logger.warning("[Ingest] Skipping malformed chunk: %s", ve.errors())
        
        # Create a new payload with only valid chunks
        payload = payload.model_copy(update={"chunks": valid_chunks})
        project_root = os.path.join(PROJECTS_ROOT, payload.project_name)

        # Auto-create project directory when first seen — mirrors config.get_project_files()
        if not os.path.exists(project_root):
            os.makedirs(project_root, exist_ok=True)
            logger.info("Auto-created project directory: %s", project_root)

        now = datetime.now(UTC).isoformat()

        is_test = any(p in payload.path.lower() for p in ["tests/", "/tests/", "test_", "/test_"])

        records: list[SkeletonChunkRecord] = [
            SkeletonChunkRecord(
                path=payload.path,
                project=payload.project_name,
                chunk_type=chunk.chunk_type,
                chunk_name=chunk.chunk_name,
                skeleton_text=chunk.skeleton_text,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                updated=now,
                is_test=is_test,
                vector=chunk.vector,
            )
            for chunk in payload.chunks
        ]

        repo = SkeletonRepository(project_root)
        return await repo.upsert_file_chunks(payload.path, payload.project_name, records, **kwargs)

    async def delete(self, path: str, project_name: str, **kwargs) -> int:
        """Removes all chunks for a deleted/moved file. Returns count deleted."""
        project_root = os.path.join(PROJECTS_ROOT, project_name)
        repo = SkeletonRepository(project_root)
        return await repo.delete_file_chunks(path, project_name, **kwargs)


# Module-level singleton — consistent with task_command_service.py pattern
skeleton_command_service = SkeletonCommandService()
