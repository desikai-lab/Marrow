from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from services.api_key_service import get_api_key_service

from transport.rest.errors import RestAuthError

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedProject:
    project: str
    key_label: str


async def authenticate_project_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedProject:
    project = request.path_params.get("project")
    if not project or credentials is None:
        raise RestAuthError()
    label = await get_api_key_service().verify(project, credentials.credentials)
    if label is None:
        raise RestAuthError()
    request.state.key_label = label
    request.state.project = project
    return AuthenticatedProject(project, label)
