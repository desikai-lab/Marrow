"""Trixie-only run for B4000282 (human-authorized 2026-09-26; no local-url leg).

Runs ensure_project + RT-04 + RT-16 + REQ-05 against ONE already-deployed
container and writes JSON for the report-append step (Task 5).

Usage (from the repository root):
    set PYTHONPATH=marrow_server
    python -m tests.qa.b4000282_trixie_comparison.run_single ^
        --url "http://<host>:<port>/mcp?token=<token>" ^
        --project MarrowTest3

Does NOT build, start, or stop any container. No Docker required here.
The full two-container comparison remains compare_images.py (Task 4),
which runs once the pinned python:3.12-slim image is deployed too.
"""

import argparse
import asyncio
import json
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from tests.qa.b4000282_trixie_comparison.checks import ensure_project, run_req05, run_rt04, run_rt16

RESULT_PATH = Path("docs/qa/_scratch/b4000282-trixie-only-result.json")


async def _run_against(url: str, project: str) -> dict:
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            setup = await ensure_project(session, project)
            return {
                "setup": setup,
                "rt04": await run_rt04(session, project),
                "rt16": await run_rt16(session, project),
                "req05": await run_req05(session, project),
            }


async def main() -> None:
    parser = argparse.ArgumentParser(description="B4000282 trixie-only check runner")
    parser.add_argument("--url", required=True)
    parser.add_argument("--project", default="MarrowTest3")
    args = parser.parse_args()

    result = {"trixie_experimental": await _run_against(args.url, args.project)}
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2))
    print(f"Wrote {RESULT_PATH}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
