import time

import pytest
from cli.services.skills_registry import (
    SkillAlreadyRegisteredError,
    SkillNotRegisteredError,
    SkillsRegistry,
)


def test_add_new_skill_creates_registry_file(tmp_path):
    registry = SkillsRegistry(str(tmp_path))
    registry.add("foo", "https://github.com/x/y")

    reg_file = tmp_path / ".skills-registry.json"
    assert reg_file.exists()

    skill = registry.get("foo")
    assert skill is not None
    assert skill["name"] == "foo"
    assert skill["source_repo"] == "https://github.com/x/y"
    assert "installed_at" in skill


def test_add_duplicate_raises_skill_already_registered_error(tmp_path):
    registry = SkillsRegistry(str(tmp_path))
    registry.add("foo", "https://github.com/x/y")
    with pytest.raises(SkillAlreadyRegisteredError):
        registry.add("foo", "https://github.com/x/y")


def test_get_existing_skill_returns_dict(tmp_path):
    registry = SkillsRegistry(str(tmp_path))
    registry.add("foo", "https://github.com/x/y")
    res = registry.get("foo")
    assert isinstance(res, dict)
    assert res["name"] == "foo"


def test_get_missing_skill_returns_none(tmp_path):
    registry = SkillsRegistry(str(tmp_path))
    assert registry.get("nonexistent") is None


def test_remove_existing_skill_deletes_entry(tmp_path):
    registry = SkillsRegistry(str(tmp_path))
    registry.add("foo", "https://github.com/x/y")
    assert registry.get("foo") is not None
    registry.remove("foo")
    assert registry.get("foo") is None


def test_remove_missing_skill_raises_skill_not_registered_error(tmp_path):
    registry = SkillsRegistry(str(tmp_path))
    with pytest.raises(SkillNotRegisteredError):
        registry.remove("nonexistent")


def test_list_all_returns_all_entries(tmp_path):
    registry = SkillsRegistry(str(tmp_path))
    registry.add("foo", "https://github.com/x/y")
    registry.add("bar", "https://github.com/x/z")
    all_skills = registry.list_all()
    assert len(all_skills) == 2
    names = [s["name"] for s in all_skills]
    assert "foo" in names
    assert "bar" in names


def test_update_timestamp_refreshes_installed_at(tmp_path):
    registry = SkillsRegistry(str(tmp_path))
    registry.add("foo", "https://github.com/x/y")

    first_time = registry.get("foo")["installed_at"]
    time.sleep(0.01)

    registry.update_timestamp("foo")
    second_time = registry.get("foo")["installed_at"]

    assert first_time != second_time


def test_load_tolerates_missing_registry_file(tmp_path):
    registry = SkillsRegistry(str(tmp_path))
    assert registry.list_all() == []


def test_load_tolerates_malformed_json(tmp_path):
    reg_file = tmp_path / ".skills-registry.json"
    with open(reg_file, "w", encoding="utf-8") as f:
        f.write("garbage content")

    registry = SkillsRegistry(str(tmp_path))
    assert registry.list_all() == []
