import os

import yaml

from migrator.migrations.local_storage_layout import REGISTRY
from services.role_profile_service import RoleProfileLoader
from tools import projects as projects_module

TEMPLATE = projects_module.TEMPLATE_DIR


def _read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


def _profiles():
    text = _read(TEMPLATE, "artifacts", "docs", "manuals", "role_profiles.yaml")
    return RoleProfileLoader().load(text)


def test_template_role_profiles_init_role_points_at_an_existing_guideline_file():
    profile = _profiles()["init"]

    assert profile.next == "discovery"
    assert profile.requires_approval is True
    assert os.path.isfile(os.path.join(TEMPLATE, "artifacts", *profile.guideline.split("/")))


def test_template_role_profiles_every_role_has_empty_adrs_and_playbooks():
    for name, profile in _profiles().items():
        assert profile.adrs == [], name
        assert profile.playbooks == [], name


def test_template_project_yaml_is_at_the_registry_head_version():
    versions = yaml.safe_load(_read(TEMPLATE, ".marrow", "project.yaml"))["schema_versions"]

    assert versions["local_storage_layout"] == max(m.to_version for m in REGISTRY) == 3


def test_registry_is_contiguous_and_ends_with_the_init_agent_step():
    steps = sorted(REGISTRY, key=lambda m: m.from_version)

    assert [(m.from_version, m.to_version) for m in steps] == [(1, 2), (2, 3)]
    assert type(steps[-1]).__name__ == "V2ToV3AddInitAgent"


def test_template_init_guideline_defines_both_protocols_and_the_rules():
    text = _read(TEMPLATE, "artifacts", "docs", "manuals", "guidelines", "init.md")

    for expected in (
        "## 2. Protocol A",
        "## 3. Protocol B",
        "Non-destructive rule",
        "requires_approval",
        "`start_role`",
    ):
        assert expected in text


def test_template_session_md_starts_at_the_discovery_agent():
    text = _read(TEMPLATE, "artifacts", "session.md")

    assert "next_agent_role:** Discovery Agent" in text
