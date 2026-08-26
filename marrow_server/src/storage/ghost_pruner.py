"""Generic ghost-record pruning: enumerate a repo's indexed paths, ask a
pluggable ExistenceStrategy whether each still exists, delete the ones that
don't. See docs/decisions/adr/0043-ghost-pruning-strategy-pattern.md.

This module has zero knowledge of SOURCE_ROOT, project_root, or any other
resolution detail -- that lives entirely inside ExistenceStrategy
implementations. As of TD4000174, the only concrete strategy is
FilesystemExistenceStrategy, and the only wired-up caller is
ArtifactChunkRepository via MaintenanceService. The skeleton ghost-pruning
call site is explicitly NOT wired to this engine -- see ADR-0043.
"""

import asyncio
import logging
from pathlib import Path
from typing import Callable, Protocol

logger = logging.getLogger("marrow.ghost_pruner")


class ExistenceStrategy(Protocol):
    """Given a project and a path already known to be indexed, report whether
    the underlying artifact/file still exists."""

    async def exists(self, project: str, path: str) -> bool: ...


class FilesystemExistenceStrategy:
    """Checks Path(root_resolver(project)) / path against the local filesystem.

    root_resolver is injected so callers decide what "root" means for their
    repo (project_root today; something SOURCE_ROOT-aware or branch-aware
    later, for a possible future skeleton strategy -- see ADR-0043).
    """

    def __init__(self, root_resolver: Callable[[str], str]):
        self._root_resolver = root_resolver

    async def exists(self, project: str, path: str) -> bool:
        root = self._root_resolver(project)
        abs_path = Path(root) / path
        return await asyncio.to_thread(abs_path.exists)


class GhostPruningRepository(Protocol):
    """Structural contract GhostPruner needs from any repo it prunes.
    ArtifactChunkRepository satisfies this by duck typing -- no inheritance
    required (dependency inversion, consistent with ADR-0038)."""

    async def count_rows(self) -> int: ...
    async def get_all_indexed_paths(self, project: str) -> list[str]: ...
    async def delete_chunks_by_path(self, path: str, project: str) -> int: ...


class GhostPruner:
    def __init__(self, repo: GhostPruningRepository, strategy: ExistenceStrategy):
        self._repo = repo
        self._strategy = strategy

    async def prune(self, project: str) -> int:
        pruned = 0
        count = await self._repo.count_rows()
        if count == 0:
            logger.info("Table is empty for %s, skipping ghost pruning.", project)
            return pruned

        for path in await self._repo.get_all_indexed_paths(project):
            if not await self._strategy.exists(project, path):
                await self._repo.delete_chunks_by_path(path, project)
                pruned += 1
                logger.debug("Pruned ghost record: %s", path)
        return pruned
