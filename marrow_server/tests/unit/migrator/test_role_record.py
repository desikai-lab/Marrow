import yaml

from migrator.migrations.local_storage_layout.role_record import INIT_PROFILE, append_init_role

NL = chr(10)
CRLF = chr(13) + chr(10)

TEMPLATE_TEXT = """roles:
  discovery:
    guideline: docs/manuals/guidelines/discovery.md
    adrs: []
    playbooks: []
    next: architecture
    requires_approval: true
  execution:
    guideline: docs/manuals/guidelines/execution.md
    adrs: []
    playbooks: []
    next: discovery
    requires_approval: false
"""

LIVE_SHAPE_TEXT = """roles:
  discovery:
    guideline: docs/manuals/guidelines/discovery.md
    adrs: ["0007", "0008"]
    playbooks:
        - skills/brainstorming/SKILL.md
    next: architecture
    requires_approval: true
  reviewer:
    guideline: docs/manuals/guidelines/reviewer.md
    adrs: []
    playbooks: []
    next: null
    requires_approval: false"""


def _roles(text):
    return yaml.safe_load(text)["roles"]


def test_append_init_role_template_shape_adds_role_and_keeps_prefix():
    result = append_init_role(TEMPLATE_TEXT)

    assert result is not None
    assert result.startswith(TEMPLATE_TEXT)
    assert _roles(result)["init"] == INIT_PROFILE
    assert list(_roles(result)) == ["discovery", "execution", "init"]


def test_append_init_role_live_shape_without_trailing_newline_adds_role_and_keeps_prefix():
    assert not LIVE_SHAPE_TEXT.endswith(NL)

    result = append_init_role(LIVE_SHAPE_TEXT)

    assert result is not None
    assert result.startswith(LIVE_SHAPE_TEXT + NL)
    assert _roles(result)["init"] == INIT_PROFILE
    assert _roles(result)["discovery"]["playbooks"] == ["skills/brainstorming/SKILL.md"]


def test_append_init_role_comments_are_preserved():
    text = (
        "# my profiles"
        + NL
        + """roles:
  # first
  discovery:
    guideline: g.md
    adrs: []
  # trailing comment
"""
    )

    result = append_init_role(text)

    assert result is not None
    assert result.startswith(text)


def test_append_init_role_crlf_text_uses_crlf_for_the_record():
    text = TEMPLATE_TEXT.replace(NL, CRLF)

    result = append_init_role(text)

    assert result is not None
    assert result.startswith(text)
    assert NL not in result.replace(CRLF, "")
    assert _roles(result)["init"] == INIT_PROFILE


def test_append_init_role_four_space_role_keys_follow_the_existing_indent():
    text = "roles:" + NL + "    discovery:" + NL + "        guideline: g.md" + NL

    result = append_init_role(text)

    assert result is not None
    assert (
        NL + "    init:" + NL + "        guideline: docs/manuals/guidelines/init.md" + NL in result
    )
    assert _roles(result)["init"] == INIT_PROFILE


def test_append_init_role_extra_top_level_key_returns_none():
    assert append_init_role(TEMPLATE_TEXT + "version: 2" + NL) is None


def test_append_init_role_init_already_present_returns_none():
    text = TEMPLATE_TEXT + "  init:" + NL + "    guideline: x.md" + NL

    assert append_init_role(text) is None


def test_append_init_role_tab_indentation_returns_none():
    assert append_init_role("roles:" + NL + chr(9) + "discovery:" + NL) is None


def test_append_init_role_inline_empty_roles_returns_none():
    assert append_init_role("roles: {}" + NL) is None


def test_append_init_role_empty_text_returns_none():
    assert append_init_role("") is None
