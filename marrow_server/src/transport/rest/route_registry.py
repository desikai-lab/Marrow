"""REST route registration: composes the route modules under transport/modules/.

Mirrors tool_registry.register_tools: each tool group is a module that exposes
use_<group>_routes(app).
"""

from fastapi import FastAPI

from transport.modules.artifact.routes import use_artifact_routes
from transport.modules.code.routes import use_code_routes
from transport.modules.session.routes import use_session_routes
from transport.modules.task.routes import use_task_routes
from transport.rest.paths import PROJECT_PREFIX
from transport.rest.routers import meta


def register_routes(app: FastAPI) -> None:
    """Mount the REST routes onto `app`."""
    use_session_routes(app)
    use_artifact_routes(app)
    app.include_router(meta.router, prefix=PROJECT_PREFIX)
    use_code_routes(app)
    use_task_routes(app)
