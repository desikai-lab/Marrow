import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

# Resolve monorepo root (3 levels up from this file: src/transport → src → marrow_worker → root)
_MONOREPO_ROOT = str(Path(__file__).parents[3])
if _MONOREPO_ROOT not in sys.path:
    sys.path.insert(0, _MONOREPO_ROOT)

from marrow_common.skeleton_schema import SCHEMA_VERSION, SkeletonChunk  # noqa: E402
from pydantic import ValidationError  # noqa: E402

logger = logging.getLogger(__name__)

class MCPClient:
    """Async client for delivering pre-vectorized skeleton chunks over HTTP."""
    def __init__(self, target_url: str, project_name: str, secret_token: str, root_dir: str, outbox=None):
        self.target_url = target_url
        self.project_name = project_name
        self.root_dir = os.path.abspath(root_dir)
        self._outbox = outbox  # WorkerOutbox | None
        # Attach the Bearer token to every request at the client level
        self.client = httpx.AsyncClient(
            base_url=target_url,
            headers={"Authorization": f"Bearer {secret_token}"},
        )

    async def close(self) -> None:
        """Cleanly tears down the underlying async connection pool."""
        await self.client.aclose()

    async def _deliver(
        self,
        row_id: int,
        operation: str,
        file_path: str,
        payload: dict,
    ) -> None:
        """
        Unified HTTP delivery function used for both immediate sends and outbox
        flush replays.

        - 2xx  → marks outbox row done (deleted).
        - 4xx  → marks outbox row FAILED (bad payload, never retried).
        - 5xx / network error → leaves row PENDING for next flush.
        """
        start_time = time.perf_counter()
        try:
            if operation == "upsert":
                response = await self.client.post("/api/vectorize", json=payload)
            else:
                response = await self.client.request("DELETE", "/api/vectorize", json=payload)

            if 400 <= response.status_code < 500:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error("[Transport] 4xx for %s (%s) — marking FAILED: %s", file_path, operation, error_msg)
                if self._outbox:
                    await self._outbox.mark_failed(row_id, error_msg)
                return

            response.raise_for_status()  # raises on 5xx
            info = response.json()
            logger.info("[Transport] OK (%s) — %s", operation, file_path)
            if operation == "upsert":
                logger.info("[Transport] %s chunk(s) stored.", info.get("chunks_stored", "?"))
            if self._outbox:
                await self._outbox.mark_done(row_id)

        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            logger.warning("[Transport] Transient error for %s — row stays PENDING: %s", file_path, e)
        except Exception as e:
            logger.warning("[Transport] Unexpected error for %s — row stays PENDING: %s", file_path, e)
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            metrics = {"layer": "client", "operation": f"MCPClient.{operation}", "duration_ms": round(duration_ms, 2)}
            logger.info(f'[PERF] {json.dumps(metrics)}')

    def _make_deliver_fn(self):
        """Returns a bound coroutine callable for use by WorkerOutbox.flush_pending()."""
        async def _fn(row_id: int, operation: str, file_path: str, payload: dict) -> None:
            await self._deliver(row_id, operation, file_path, payload)
        return _fn

    async def send_chunks(
        self,
        absolute_filepath: str,
        file_summary: str,
        chunks: list[dict[str, Any]],
    ) -> None:
        """
        Computes the repo-relative path and POSTs the chunk-based skeleton
        payload to POST /api/vectorize on the remote marrow_server server.

        Each dict in `chunks` must contain:
            type          (str)         - code unit kind: "namespace", "class", "method", etc.
            name          (str)         - qualified identifier, e.g. "ProcessOrder"
            skeleton_text (str)         - extracted skeleton text for this unit
            vector        (List[float]) - pre-computed embedding (384 floats)
            line_start    (int)         - 1-indexed start line in the source file
            line_end      (int)         - 1-indexed end line in the source file
        """
        # Validate each chunk against the shared transport contract (ADR TD4000076)
        validated = []
        for chunk in chunks:
            # Map input field names to SkeletonChunk internal names if needed
            # The input from Skeletonizer has: type, name, line_start, line_end
            # SkeletonChunk expects: chunk_type, chunk_name, start_line, end_line
            # We map them here before validation to maintain schema consistency
            data = {
                "path": os.path.relpath(absolute_filepath, start=self.root_dir).replace("\\", "/"),
                "project": self.project_name,
                "chunk_type": chunk.get("type"),
                "chunk_name": chunk.get("name"),
                "skeleton_text": chunk.get("skeleton_text"),
                "vector": chunk.get("vector"),
                "start_line": chunk.get("line_start"),
                "end_line": chunk.get("line_end"),
                "file_summary": file_summary
            }
            try:
                SkeletonChunk(**data)
                validated.append(chunk)
            except ValidationError as ve:
                logger.warning(
                    "[Transport] Skipping malformed chunk in %s: %s",
                    absolute_filepath, ve.errors()
                )
        chunks = validated
        rel_path = os.path.relpath(absolute_filepath, start=self.root_dir).replace("\\", "/")

        payload = {
            "schema_version": SCHEMA_VERSION,
            "project_name": self.project_name,
            "path":         rel_path,
            "file_summary": file_summary,
            "chunks":       chunks,
        }

        if self._outbox:
            row_id = await self._outbox.enqueue("upsert", rel_path, len(chunks), payload)
            await self._deliver(row_id, "upsert", rel_path, payload)
        else:
            try:
                response = await self.client.post("/api/vectorize", json=payload)
                response.raise_for_status()
                info = response.json()
                logger.info(
                    "[Transport] OK — %s chunk(s) stored for %s",
                    info.get('chunks_stored', '?'), rel_path
                )
            except Exception as e:
                logger.error("[Transport] Failed to deliver skeleton for %s: %s", rel_path, e)

    async def delete_chunks(self, absolute_filepath: str) -> None:
        """
        Notifies the MCP server that a source file has been deleted or moved.
        Converts the absolute path to a repo-relative path (identical to send_chunks)
        and calls DELETE /api/vectorize.
        """
        rel_path = os.path.relpath(absolute_filepath, start=self.root_dir).replace("\\", "/")
        payload = {"project_name": self.project_name, "path": rel_path}
        if self._outbox:
            row_id = await self._outbox.enqueue("delete", rel_path, 0, payload)
            await self._deliver(row_id, "delete", rel_path, payload)
        else:
            try:
                response = await self.client.request("DELETE", "/api/vectorize", json=payload)
                response.raise_for_status()
                info = response.json()
                logger.info("[Transport] Deleted chunk(s) for %s: %s", rel_path, info)
            except Exception as e:
                logger.error("[Transport] Failed to delete skeleton for %s: %s", rel_path, e)
