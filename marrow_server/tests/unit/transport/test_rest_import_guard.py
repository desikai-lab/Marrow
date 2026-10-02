import ast
from pathlib import Path

import transport.rest as rest_pkg

FORBIDDEN = {
    "transport.middleware",
    "transport.app_factory",
    "transport.oauth_router",
    "utils.error_middleware",
}


def _sources():
    return sorted(Path(rest_pkg.__file__).parent.rglob("*.py"))


def test_rest_package_does_not_import_legacy_transport_modules():
    offenders = []
    for path in _sources():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [f"{node.module}.{a.name}" for a in node.names]
            offenders += [f"{path.name}: {n}" for n in names if n in FORBIDDEN]
    assert offenders == []


def test_rest_package_never_references_the_global_token():
    for path in _sources():
        assert "SECRET_TOKEN" not in path.read_text(encoding="utf-8"), path.name
