import asyncio

import pytest
from flag_matrix import combinations_of, ids, set_flags
from mcp.server.fastmcp import FastMCP
from transport.modules.build.tools import use_build_tools
from transport.modules.code.tools import use_code_tools
from transport.modules.task.tools import use_task_tools
from transport.tool_registry import register_tools

GROUP_TOOLS = {
    "task": {"add_tasks", "search_tasks", "get_task_details", "update_task", "complete_tasks"},
    "code": {"search_code_skeletons", "get_file_skeleton", "get_project_map", "view_file_source"},
    "build": {"run_project_build"},
}
COMBINATIONS = combinations_of(GROUP_TOOLS)


def _served() -> dict[str, str]:
    server = FastMCP("registry-flags-test")
    register_tools(server)
    return {t.name: t.description for t in asyncio.run(server.list_tools())}


def test_register_tools_all_groups_enabled_registers_24_tools(monkeypatch):
    set_flags(monkeypatch, frozenset())
    assert len(_served()) == 24


@pytest.mark.parametrize("disabled", COMBINATIONS, ids=ids)
def test_register_tools_group_off_equals_default_minus_group_tools(monkeypatch, disabled):
    set_flags(monkeypatch, frozenset())
    default = set(_served())
    set_flags(monkeypatch, disabled)
    removed = set().union(*(GROUP_TOOLS[g] for g in disabled))
    assert set(_served()) == default - removed


@pytest.mark.parametrize(
    "use,group",
    [(use_code_tools, "code"), (use_task_tools, "task"), (use_build_tools, "build")],
)
def test_use_tools_group_off_registers_nothing(monkeypatch, use, group):
    set_flags(monkeypatch, frozenset({group}))
    server = FastMCP("module-off-test")
    use(server)
    assert asyncio.run(server.list_tools()) == []


def test_register_tools_group_off_leaves_remaining_descriptions_unchanged(monkeypatch):
    set_flags(monkeypatch, frozenset())
    default = _served()
    set_flags(monkeypatch, frozenset(GROUP_TOOLS))
    served = _served()
    assert len(served) == 14
    assert all(served[name] == default[name] for name in served)
