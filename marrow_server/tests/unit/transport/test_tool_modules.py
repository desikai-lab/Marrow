import asyncio

import pytest
from mcp.server.fastmcp import FastMCP
from transport.modules.artifact.tools import use_artifact_tools
from transport.modules.build.tools import use_build_tools
from transport.modules.code.tools import use_code_tools
from transport.modules.history.tools import use_history_tools
from transport.modules.project.tools import use_project_tools
from transport.modules.session.tools import use_session_tools
from transport.modules.task.tools import use_task_tools
from transport.tool_registry import register_tools


def _use_artifact(server):
    use_artifact_tools(server)


MODULES = [
    pytest.param(
        _use_artifact,
        'ARTIFACT',
        {
            'semantic_search',
            'read_project_artifacts',
            'save_project_artifacts',
            'list_project_artifacts',
            'move_project_artifact',
            'delete_project_artifact',
            'search_project_artifacts',
            'get_project_artifact_outline',
        },
        id='artifact',
    ),
    pytest.param(
        use_history_tools,
        'HISTORY',
        {'list_artifact_history', 'restore_project_artifact'},
        id='history',
    ),
    pytest.param(
        use_session_tools, 'SESSION', {'get_session_context', 'get_guideline'}, id='session'
    ),
    pytest.param(use_project_tools, 'PROJECT', {'list_projects', 'init_project'}, id='project'),
    pytest.param(
        use_code_tools,
        'CODE',
        {'search_code_skeletons', 'get_file_skeleton', 'get_project_map', 'view_file_source'},
        id='code',
    ),
    pytest.param(
        use_task_tools,
        'TASK',
        {'add_tasks', 'search_tasks', 'get_task_details', 'update_task', 'complete_tasks'},
        id='task',
    ),
    pytest.param(use_build_tools, 'BUILD', {'run_project_build'}, id='build'),
]


def _served(use) -> dict[str, str]:
    server = FastMCP('tool-modules-test')
    use(server)
    return {t.name: t.description for t in asyncio.run(server.list_tools())}


@pytest.mark.parametrize('use,tag,names', MODULES)
def test_use_tools_registers_exactly_the_module_tools_with_matching_tag(use, tag, names):
    served = _served(use)
    assert set(served) == names
    assert all(text.lstrip().startswith(f'[{tag} TOOLS]') for text in served.values())


def test_module_tool_sets_are_disjoint_and_cover_24_tools():
    sets = [param.values[2] for param in MODULES]
    assert sum(len(s) for s in sets) == 24
    assert len(set().union(*sets)) == 24


def test_register_tools_registers_the_union_of_all_modules():
    server = FastMCP('tool-modules-union')
    register_tools(server)
    names = {t.name for t in asyncio.run(server.list_tools())}
    assert names == set().union(*(param.values[2] for param in MODULES))
