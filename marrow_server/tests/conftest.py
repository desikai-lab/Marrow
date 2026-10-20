"""Suite precondition: no effective TOOL_GROUP_* override (F4000302 implementation plan).

config.py loads .env with load_dotenv(), which never overrides an existing variable,
so pinning the three flags here keeps a developer's local .env (used to try the flags
on a running server) from changing the default tool surface the tests assert.
Pinning happens in pytest_configure, which runs before any test module imports config
(pyproject.toml sets testpaths = ["tests"], so this is an initial conftest).
Flag tests do not read the environment; they monkeypatch config.<FLAG> directly.
"""

import os

TOOL_GROUP_FLAGS = (
    "TOOL_GROUP_CODE_ENABLED",
    "TOOL_GROUP_TASK_ENABLED",
    "TOOL_GROUP_BUILD_ENABLED",
)


def pytest_configure(config):
    for flag in TOOL_GROUP_FLAGS:
        os.environ.setdefault(flag, "true")
