from fastapi import FastAPI
from transport.modules.artifact.routes import use_artifact_routes
from transport.modules.code.routes import use_code_routes
from transport.modules.session.routes import use_session_routes
from transport.modules.task.routes import use_task_routes
from transport.rest.route_registry import register_routes

TASK_OPERATIONS = {'add_tasks', 'search_tasks', 'get_task_details', 'update_task', 'complete_tasks'}
CODE_OPERATIONS = {
    'search_code_skeletons',
    'get_file_skeleton',
    'get_project_map',
    'view_file_source',
}
CORE_OPERATIONS = {
    'get_session_context',
    'get_guideline',
    'read_project_artifacts',
    'save_project_artifacts',
    'list_project_artifacts',
    'move_project_artifact',
    'delete_project_artifact',
    'search_project_artifacts',
    'get_project_artifact_outline',
    'semantic_search',
    'list_artifact_history',
    'restore_project_artifact',
}


def _operations(*uses) -> set[str]:
    app = FastAPI(generate_unique_id_function=lambda route: route.name)
    for use in uses:
        use(app)
    spec = app.openapi()
    return {op['operationId'] for methods in spec['paths'].values() for op in methods.values()}


def test_task_routes_serve_exactly_the_task_operations():
    assert _operations(use_task_routes) == TASK_OPERATIONS


def test_code_routes_serve_exactly_the_code_operations():
    assert _operations(use_code_routes) == CODE_OPERATIONS


def test_core_route_modules_serve_the_twelve_core_operations():
    assert _operations(use_session_routes, use_artifact_routes) == CORE_OPERATIONS


def test_register_routes_serves_all_21_operations_of_the_default_surface():
    app = FastAPI(generate_unique_id_function=lambda route: route.name)
    register_routes(app)
    spec = app.openapi()
    operations = {op['operationId'] for methods in spec['paths'].values() for op in methods.values()}
    assert operations == TASK_OPERATIONS | CODE_OPERATIONS | CORE_OPERATIONS
    assert len(operations) == 21
