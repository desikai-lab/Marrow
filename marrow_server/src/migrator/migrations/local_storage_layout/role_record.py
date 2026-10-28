"""Pure text helpers for adding the init role to a user-edited role_profiles.yaml. No I/O."""

import re

import yaml

INIT_ROLE = "init"
_GUIDELINE = "docs/manuals/guidelines/init.md"
_NEXT = "discovery"
INIT_PROFILE: dict = {
    "guideline": _GUIDELINE,
    "adrs": [],
    "playbooks": [],
    "next": _NEXT,
    "requires_approval": True,
}

_ROLES_HEADER_RE = re.compile(r"^roles:[ \t]*(?:#.*)?$")
_ROLE_KEY_RE = re.compile(r"^(?P<indent>[ ]+)[A-Za-z_][\w-]*:[ \t]*(?:#.*)?$")
_CRLF = "\r\n"
_LF = "\n"


def _detect_role_indent(text: str) -> str | None:
    """Indent of the first role key under `roles:`, or None when the layout is not recognised."""
    in_roles = False
    for line in text.splitlines():
        if not in_roles:
            in_roles = bool(_ROLES_HEADER_RE.match(line))
            continue
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _ROLE_KEY_RE.match(line)
        return match.group("indent") if match else None
    return None


def _render_record(indent: str, newline: str) -> str:
    inner = indent * 2
    lines = [
        f"{indent}{INIT_ROLE}:",
        f"{inner}guideline: {_GUIDELINE}",
        f"{inner}adrs: []",
        f"{inner}playbooks: []",
        f"{inner}next: {_NEXT}",
        f"{inner}requires_approval: true",
    ]
    return newline.join(lines) + newline


def append_init_role(text: str) -> str | None:
    """Return text with the init role record appended, or None when appending is not safe.

    Safe means: valid YAML, top-level keys exactly ['roles'], roles is a mapping without an
    init role, the first role key sits on an indented line, and the result re-parses to the
    old roles plus init. Existing text is never changed; the record is only appended.
    """
    try:
        old = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if not isinstance(old, dict) or list(old) != ["roles"]:
        return None
    roles = old["roles"]
    if not isinstance(roles, dict) or INIT_ROLE in roles:
        return None
    indent = _detect_role_indent(text)
    if indent is None:
        return None
    newline = _CRLF if _CRLF in text else _LF
    base = text if text.endswith(_LF) else text + newline
    candidate = base + _render_record(indent, newline)
    try:
        new = yaml.safe_load(candidate)
    except yaml.YAMLError:
        return None
    if new != {"roles": {**roles, INIT_ROLE: INIT_PROFILE}}:
        return None
    return candidate
