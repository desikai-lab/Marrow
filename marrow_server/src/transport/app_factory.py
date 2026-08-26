import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp_core import mcp
from storage.db import index_rebuild_worker

from transport.middleware import (
    DebugLoggingMiddleware,
    FixHostHeaderMiddleware,
    SSEHeadersMiddleware,
    TimingMiddleware,
    TokenAuthMiddleware,
)
from transport.oauth_router import router as oauth_router
from transport.vectorize_router import router as vectorize_router

# Build the MCP ASGI application.
mcp_asgi = mcp.streamable_http_app()

import logging as _logging  # noqa: E402


async def maintenance_loop() -> None:
    """Background task: runs MaintenanceService for all known projects every N hours.

    Sleep-first design ensures startup and initial marrow_worker scans
    are never interrupted. Per-project errors are isolated — one failure never
    aborts the cycle or kills the loop.
    """
    import os

    from config import PROJECTS_ROOT
    from services.maintenance_service import MaintenanceService
    from storage.repositories.skeleton_repository import SkeletonRepository

    interval = int(os.getenv("MAINTENANCE_INTERVAL_SECONDS", "1800"))
    _logger = _logging.getLogger("marrow.maintenance_scheduler")
    _logger.info("[Maintenance] Scheduler started. Interval: %ds.", interval)

    while True:
        await asyncio.sleep(interval)

        if not os.path.isdir(PROJECTS_ROOT):
            _logger.warning("[Maintenance] PROJECTS_ROOT not found, skipping cycle.")
            continue

        projects = [
            p for p in os.listdir(PROJECTS_ROOT) if os.path.isdir(os.path.join(PROJECTS_ROOT, p))
        ]
        _logger.info("[Maintenance] Cycle start — %d project(s).", len(projects))

        for project_name in projects:
            project_root = os.path.join(PROJECTS_ROOT, project_name)
            db_path = os.path.join(project_root, ".db", "index.lancedb")
            if not os.path.exists(db_path):
                _logger.debug("[Maintenance] Skipping %s: no DB found.", project_name)
                continue
            try:
                from storage.ghost_pruner import FilesystemExistenceStrategy, GhostPruner
                from storage.repositories.artifact_repository import ArtifactChunkRepository

                repo = SkeletonRepository(project_root)

                artifact_chunk_repo = ArtifactChunkRepository(project_root)
                artifact_strategy = FilesystemExistenceStrategy(
                    root_resolver=lambda project: os.path.join(PROJECTS_ROOT, project, "artifacts")
                )

                artifact_pruner = GhostPruner(repo=artifact_chunk_repo, strategy=artifact_strategy)

                service = MaintenanceService(
                    project_root=project_root,
                    project_name=project_name,
                    skeleton_repo=repo,
                    artifact_ghost_pruner=artifact_pruner,
                )
                report = await service.run()
                _logger.info(
                    "[Maintenance] %s — compact: %s, versions: %s, ghosts: %d, "
                    "artifact_chunks_pruned: %d, errors: %d",
                    project_name,
                    report.files_compacted,
                    report.versions_cleaned,
                    report.ghosts_pruned,
                    report.artifact_chunks_pruned,
                    len(report.errors),
                )
                if report.errors:
                    _logger.warning("[Maintenance] %s errors: %s", project_name, report.errors)
            except Exception as e:
                _logger.error("[Maintenance] Failed for %s: %s", project_name, e)

        _logger.info("[Maintenance] Cycle complete.")


@asynccontextmanager
async def lifespan(app):
    # Launch background index rebuild workers (PERF-02)
    tasks = [
        asyncio.create_task(index_rebuild_worker("code_skeleton_index", debounce_s=20)),
        asyncio.create_task(index_rebuild_worker("artifact_chunks", debounce_s=20)),
        asyncio.create_task(maintenance_loop()),
    ]

    async with mcp.session_manager.run():
        yield

    # Shutdown logic: cancel tasks and wait for them to finish
    for t in tasks:
        t.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def create_app() -> FastAPI:
    app = FastAPI(title="Marrow MCP Server", lifespan=lifespan)

    # Include routers
    app.include_router(oauth_router)
    app.include_router(vectorize_router)

    # Register CORSMiddleware (present in original app.py but skipped in plan B-5 snippet)
    # Keeping it as it's critical for browser-based MCP clients like Claude Desktop or web UIs.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["WWW-Authenticate", "mcp-protocol-version"],
    )

    # MIDDLEWARE REGISTRATION ORDER — ORDER IS LOAD-SENSITIVE (ADR-01)
    # Starlette applies middleware in reverse registration order.
    # Last registered = outermost wrapper = first to process the request.
    #
    # Runtime execution order (outermost → innermost):
    #   1. FixHostHeaderMiddleware  — rewrites Host header before auth validation
    #   2. SSEHeadersMiddleware     — injects SSE headers
    #   3. TokenAuthMiddleware      — authenticates after host is corrected
    #      → handler
    #
    # DebugLoggingMiddleware exists in middleware.py but is NOT registered here
    # per plan_track_b.md instructions (even though it was registered in original app.py).
    #
    # WARNING: Do not reorder these three calls without updating this comment and ADR-01.
    app.add_middleware(TokenAuthMiddleware)  # innermost at runtime
    app.add_middleware(SSEHeadersMiddleware)
    app.add_middleware(FixHostHeaderMiddleware)
    if os.getenv("MCP_DEBUG_TRANSPORT", "false").lower() == "true":
        app.add_middleware(DebugLoggingMiddleware)  # outermost at runtime
    app.add_middleware(TimingMiddleware)  # absolute outermost wrapper for latency tracking

    # Mount MCP SSE transport
    app.mount("/", mcp_asgi)

    return app


app = create_app()
