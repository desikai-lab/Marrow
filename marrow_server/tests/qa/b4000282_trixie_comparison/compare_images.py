"""Runs RT-04 + RT-16 + REQ-05 against two already-running, already-deployed
containers and writes a combined JSON result for the report-append step (Task 5).

Usage:
    python -m tests.qa.b4000282_trixie_comparison.compare_images \\
        --trixie-url http://<local-server-host>:<port1>/mcp \\
        --local-url  http://<local-server-host>:<port2>/mcp \\
        --token "$SECRET_TOKEN" \\
        --project BacklogMCP

Does NOT build, start, or stop any container. Both images are built and
published by .github/workflows/build-b4000282-trixie-comparison.yml (Task 2)
and deployed by the human on their own local server -- this script only needs
two reachable URLs and the shared SECRET_TOKEN. No Docker required here.
"""

import argparse
import asyncio
import json
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from tests.qa.b4000282_trixie_comparison.checks import ensure_project, run_req05, run_rt04, run_rt16

RESULT_PATH = Path("docs/qa/_scratch/b4000282-comparison-result.json")


async def _run_against(url: str, token: str, project: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
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
    parser = argparse.ArgumentParser(description="B4000282 trixie-vs-local comparison runner")
    parser.add_argument("--trixie-url", required=True)
    parser.add_argument("--local-url", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--project", default="MarrowTest3")
    args = parser.parse_args()

    trixie_result = await _run_against(args.trixie_url, args.token, args.project)
    local_result = await _run_against(args.local_url, args.token, args.project)

    combined = {"trixie_experimental": trixie_result, "python312_slim_pinned": local_result}
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(combined, indent=2))
    print(f"Wrote {RESULT_PATH}")
    print(json.dumps(combined, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
