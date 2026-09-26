"""RT-04 / RT-16 / REQ-05 check implementations for B4000282.

Each function takes an already-connected mcp.ClientSession and a project name,
calls the relevant tool(s), and returns a plain dict describing the outcome --
shape (list vs dict), error_type if any, and timing where relevant. No Docker
or transport-address knowledge lives here; that is compare_images.py's job
(Task 4), so these functions run unchanged against the in-process self-test
(this file's own tests) and against real deployed containers.
"""

import json
import re
import time
import uuid

RT16_PROBE_PATH = "docs/qa/_scratch/rt16-probe.md"

DEFAULT_PROJECT = "MarrowTest3"


async def ensure_project(session, project: str) -> dict:
    """Create-then-test setup step (human-ordered 2026-09-26): guarantees the
    comparison project exists before any RT-04/RT-16/REQ-05 check runs.

    Lists projects; if `project` is missing, creates it via `init_project`
    (fresh project mirrors the original MarrowTest3 repro conditions).
    Returns {"created": bool}."""
    raw = await _call_tool(session, "list_projects", {})
    names = raw if isinstance(raw, list) else []
    if project in names:
        return {"created": False}
    await _call_tool(session, "init_project", {"project": project})
    return {"created": True}


def _classify(raw) -> dict:
    if isinstance(raw, dict) and "error_type" in raw:
        return {"shape": "dict", "error_type": raw["error_type"]}
    if isinstance(raw, list):
        return {"shape": "list", "error_type": None}
    return {"shape": "unknown", "error_type": None}


def _unwrap_structured(raw) -> object:
    # Newer MCP SDKs wrap tool output: {"result": <actual payload>}.
    if isinstance(raw, dict) and set(raw.keys()) == {"result"}:
        return raw["result"]
    return raw


def _coerce_content(content) -> object:
    """Parse stdio text content items into plain Python objects.

    Over streamable HTTP the SDK populates result.structuredContent; over
    stdio it is None and payloads arrive as JSON text items (one item per
    list element for list results).
    """
    items = []
    for item in content or []:
        text = getattr(item, "text", None)
        if text is None:
            items.append(item)
            continue
        try:
            items.append(json.loads(text))
        except (ValueError, TypeError):
            items.append(text)
    if len(items) == 1:
        return items[0]
    return items


async def _call_tool(session, name: str, arguments: dict):
    result = await session.call_tool(name, arguments)
    if result.structuredContent is not None:
        return _unwrap_structured(result.structuredContent)
    return _coerce_content(result.content)


async def run_rt04(session, project: str) -> dict:
    variants = {
        "v1_recursive_false": {"project": project, "recursive": False},
        "v2_recursive_true": {"project": project, "recursive": True},
        "v3_path_docs_recursive_true": {"project": project, "path": "docs", "recursive": True},
    }
    results = {}
    for name, args in variants.items():
        raw = await _call_tool(session, "list_project_artifacts", args)
        results[name] = _classify(raw)
    return results


async def run_rt16(session, project: str) -> dict:
    marker = f"B4000282 RT-16 probe {uuid.uuid4()}"
    started = time.monotonic()
    write_timed_out = False
    try:
        await _call_tool(
            session,
            "save_project_artifacts",
            {
                "project": project,
                "updates": [{"path": RT16_PROBE_PATH, "mode": "replace_file", "content": marker}],
            },
        )
    except TimeoutError:
        write_timed_out = True
    elapsed = time.monotonic() - started

    readback_confirmed = False
    try:
        raw = await _call_tool(
            session,
            "read_project_artifacts",
            {"project": project, "reads": [{"path": RT16_PROBE_PATH, "mode": "full"}]},
        )
        readback_confirmed = any(
            marker in str(item) for item in (raw if isinstance(raw, list) else [raw])
        )
    except Exception:
        readback_confirmed = False
    finally:
        try:
            await _call_tool(
                session, "delete_project_artifact", {"project": project, "path": RT16_PROBE_PATH}
            )
        except Exception:
            pass

    return {
        "write_timed_out": write_timed_out,
        "elapsed_seconds": round(elapsed, 3),
        "readback_confirmed": readback_confirmed,
    }


async def run_req05(session, project: str) -> dict:
    """Forces get_dir_path() to raise ProjectFileError before _collect() runs --
    targets marrow_server/src/common/path_resolver.py:60-68 directly.

    Two possible outcomes, both proving the dict/list contract mismatch:
    - {"shape": "dict", ...}: the error dict reached the client (server with
      a widened output contract).
    - {"shape": "schema_rejection", ...}: FastMCP output-schema validation
      rejected the error dict (declared list[...] vs actual dict) and the
      client got a list_type validation error text instead -- the exact RT-04
      production signature.
    """
    raw = await _call_tool(
        session,
        "list_project_artifacts",
        {"project": project, "path": "../outside-project-root", "recursive": False},
    )
    if isinstance(raw, dict):
        return _classify(raw)
    text = raw if isinstance(raw, str) else str(raw)
    error_type = None
    match = re.search(r"""['"]error_type['"]\s*:\s*['"](\w+)['"]""", text)
    if match:
        error_type = match.group(1)
    return {
        "shape": "schema_rejection",
        "error_type": error_type,
        "signature": "list_type" if "list_type" in text else None,
        "detail": text[:500],
    }
