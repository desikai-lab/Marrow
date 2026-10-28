from unittest.mock import patch

import pytest

from migrator.migrations.local_storage_layout.v2_to_v3_add_init_agent import V2ToV3AddInitAgent
from services.role_profile_service import RoleProfileLoader

BOM = bytes([0xEF, 0xBB, 0xBF])
TEMPLATE_INIT_MD = "INIT TEMPLATE TEXT\n"


def _write(path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_apply_copies_init_md_and_appends_role_to_project_root(tmp_path, monkeypatch):
    project = tmp_path / "Proj"
    (project / "artifacts" / "docs" / "manuals").mkdir(parents=True)
    (project / "artifacts" / "docs" / "manuals" / "role_profiles.yaml").write_bytes(
        b"roles:\n  discovery:\n    guideline: g.md\n    adrs: []\n    playbooks: []\n"
    )
    tpl = tmp_path / "tpl"
    _write(
        tpl / "artifacts" / "docs" / "manuals" / "guidelines" / "init.md",
        TEMPLATE_INIT_MD.encode("utf-8"),
    )
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))

    with patch("tools.projects.TEMPLATE_DIR", str(tpl)):
        report = V2ToV3AddInitAgent().apply(str(project))

    assert report.moved == 2
    assert report.errors == []
    assert report.collisions == 0
    assert report.skipped == 0
    target_md = project / "artifacts" / "docs" / "manuals" / "guidelines" / "init.md"
    assert target_md.read_bytes() == TEMPLATE_INIT_MD.encode("utf-8")
    roles_text = (project / "artifacts" / "docs" / "manuals" / "role_profiles.yaml").read_bytes()
    assert roles_text.startswith(BOM)
    profiles = RoleProfileLoader().load(roles_text.decode("utf-8-sig"))
    assert profiles["init"].guideline == "docs/manuals/guidelines/init.md"
    assert profiles["init"].next == "discovery"
    assert profiles["init"].requires_approval is True


def test_apply_dry_run_writes_nothing(tmp_path, monkeypatch):
    project = tmp_path / "Proj"
    (project / "artifacts" / "docs" / "manuals").mkdir(parents=True)
    rp = project / "artifacts" / "docs" / "manuals" / "role_profiles.yaml"
    rp.write_bytes(b"roles:\n  discovery:\n    guideline: g.md\n    adrs: []\n    playbooks: []\n")
    tpl = tmp_path / "tpl"
    _write(
        tpl / "artifacts" / "docs" / "manuals" / "guidelines" / "init.md",
        TEMPLATE_INIT_MD.encode("utf-8"),
    )
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))

    with patch("tools.projects.TEMPLATE_DIR", str(tpl)):
        report = V2ToV3AddInitAgent().apply(str(project), dry_run=True)

    assert report.moved == 2
    assert (
        rp.read_bytes()
        == b"roles:\n  discovery:\n    guideline: g.md\n    adrs: []\n    playbooks: []\n"
    )
    assert not (project / "artifacts" / "docs" / "manuals" / "guidelines" / "init.md").exists()


def test_apply_idempotent_second_run_skips_both(tmp_path, monkeypatch):
    project = tmp_path / "Proj"
    (project / "artifacts" / "docs" / "manuals").mkdir(parents=True)
    (project / "artifacts" / "docs" / "manuals" / "role_profiles.yaml").write_bytes(
        b"roles:\n  discovery:\n    guideline: g.md\n    adrs: []\n    playbooks: []\n"
    )
    tpl = tmp_path / "tpl"
    _write(
        tpl / "artifacts" / "docs" / "manuals" / "guidelines" / "init.md",
        TEMPLATE_INIT_MD.encode("utf-8"),
    )
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))

    with patch("tools.projects.TEMPLATE_DIR", str(tpl)):
        first = V2ToV3AddInitAgent().apply(str(project))
        second = V2ToV3AddInitAgent().apply(str(project))

    assert first.moved == 2
    assert second.moved == 0
    assert second.skipped == 2


def test_apply_never_overwrites_existing_init_md(tmp_path, monkeypatch):
    project = tmp_path / "Proj"
    (project / "artifacts" / "docs" / "manuals" / "guidelines").mkdir(parents=True)
    target = project / "artifacts" / "docs" / "manuals" / "guidelines" / "init.md"
    target.write_bytes(b"CUSTOM\n")
    (project / "artifacts" / "docs" / "manuals" / "role_profiles.yaml").write_bytes(
        b"roles:\n  discovery:\n    guideline: g.md\n    adrs: []\n    playbooks: []\n"
    )
    tpl = tmp_path / "tpl"
    _write(
        tpl / "artifacts" / "docs" / "manuals" / "guidelines" / "init.md",
        TEMPLATE_INIT_MD.encode("utf-8"),
    )
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))

    with patch("tools.projects.TEMPLATE_DIR", str(tpl)):
        report = V2ToV3AddInitAgent().apply(str(project))

    assert target.read_bytes() == b"CUSTOM\n"
    assert report.moved == 1


def test_apply_different_init_role_is_collision_no_write(tmp_path, monkeypatch):
    project = tmp_path / "Proj"
    (project / "artifacts" / "docs" / "manuals").mkdir(parents=True)
    rp = project / "artifacts" / "docs" / "manuals" / "role_profiles.yaml"
    rp.write_bytes(
        b"roles:\n  discovery:\n    guideline: g.md\n    adrs: []\n    playbooks: []\n  init:\n    guideline: other.md\n    adrs: []\n    playbooks: []\n    next: x\n    requires_approval: false\n"
    )
    tpl = tmp_path / "tpl"
    _write(
        tpl / "artifacts" / "docs" / "manuals" / "guidelines" / "init.md",
        TEMPLATE_INIT_MD.encode("utf-8"),
    )
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))

    with patch("tools.projects.TEMPLATE_DIR", str(tpl)):
        report = V2ToV3AddInitAgent().apply(str(project))

    assert report.collisions == 1
    assert report.errors == []
    assert "other.md" in rp.read_text(encoding="utf-8-sig")


def test_apply_missing_template_init_raises_filenotfound(tmp_path, monkeypatch):
    project = tmp_path / "Proj"
    (project / "artifacts" / "docs" / "manuals").mkdir(parents=True)
    (project / "artifacts" / "docs" / "manuals" / "role_profiles.yaml").write_bytes(
        b"roles:\n  discovery:\n    guideline: g.md\n    adrs: []\n    playbooks: []\n"
    )
    tpl = tmp_path / "tpl"
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))

    with patch("tools.projects.TEMPLATE_DIR", str(tpl)):
        with pytest.raises(FileNotFoundError):
            V2ToV3AddInitAgent().apply(str(project))


def test_apply_unsafe_role_profiles_records_error_without_touching_session(tmp_path, monkeypatch):
    project = tmp_path / "Proj"
    (project / "artifacts").mkdir(parents=True)
    (project / "artifacts" / "session.md").write_bytes(b"x")
    (project / "artifacts" / "docs" / "manuals").mkdir(parents=True)
    rp = project / "artifacts" / "docs" / "manuals" / "role_profiles.yaml"
    rp.write_bytes(b"roles: {}\n")
    tpl = tmp_path / "tpl"
    _write(
        tpl / "artifacts" / "docs" / "manuals" / "guidelines" / "init.md",
        TEMPLATE_INIT_MD.encode("utf-8"),
    )
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))

    with patch("tools.projects.TEMPLATE_DIR", str(tpl)):
        report = V2ToV3AddInitAgent().apply(str(project))

    assert any("manual step" in str(e) for e in report.errors)
    assert rp.read_bytes() == b"roles: {}\n"
    assert (project / "artifacts" / "session.md").read_bytes() == b"x"
