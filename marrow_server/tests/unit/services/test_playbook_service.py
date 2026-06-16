from unittest.mock import patch

from services import playbook_service


def test_load_yaml_missing_returns_empty():
    with patch("services.playbook_service.read_artifact_logic", side_effect=Exception("not found")):
        res = playbook_service.load("test_proj", "execution")
        assert res == ""


def test_load_unknown_role_returns_empty():
    yaml_content = "roles:\n  execution:\n    guideline: g.md\n"
    with patch("services.playbook_service.read_artifact_logic", return_value=yaml_content):
        res = playbook_service.load("test_proj", "planning")
        assert res == ""


def test_load_no_playbooks_returns_empty():
    yaml_content = "roles:\n  execution:\n    guideline: g.md\n    playbooks: []\n"
    with patch("services.playbook_service.read_artifact_logic", return_value=yaml_content):
        res = playbook_service.load("test_proj", "execution")
        assert res == ""


def test_load_reads_playbooks_successfully():
    yaml_content = "roles:\n  execution:\n    guideline: g.md\n    playbooks:\n      - docs/playbooks/pb1.md\n      - docs/playbooks/pb2.md\n"

    def mock_read(project, rel_path, mode="full"):
        if rel_path == "docs/manuals/role_profiles.yaml":
            return yaml_content
        elif rel_path == "docs/playbooks/pb1.md":
            return '---\ntitle: "Playbook 1"\ndescription: "First description"\n---\nbody'
        elif rel_path == "docs/playbooks/pb2.md":
            return '---\ntitle: "Playbook 2"\ndescription: "Second description"\n---\nbody'
        raise Exception("unexpected path")

    with patch("services.playbook_service.read_artifact_logic", side_effect=mock_read):
        res = playbook_service.load("test_proj", "execution")
        assert "Use `read_project_artifacts` to load a skill by path" in res
        assert "- Playbook 1 [docs/playbooks/pb1.md]" in res
        assert "  First description" in res
        assert "- Playbook 2 [docs/playbooks/pb2.md]" in res
        assert "  Second description" in res


def test_load_skips_failed_playbook_reads():
    yaml_content = "roles:\n  execution:\n    guideline: g.md\n    playbooks:\n      - docs/playbooks/pb1.md\n      - docs/playbooks/pb2.md\n"

    def mock_read(project, rel_path, mode="full"):
        if rel_path == "docs/manuals/role_profiles.yaml":
            return yaml_content
        elif rel_path == "docs/playbooks/pb1.md":
            return '---\ntitle: "Playbook 1"\ndescription: "First description"\n---\nbody'
        else:
            raise Exception("simulate file read error")

    with patch("services.playbook_service.read_artifact_logic", side_effect=mock_read):
        res = playbook_service.load("test_proj", "execution")
        assert "- Playbook 1 [docs/playbooks/pb1.md]" in res
        assert "docs/playbooks/pb2.md" not in res


def test_load_returns_rich_stub_with_description():
    yaml_content = (
        "roles:\n  execution:\n    guideline: g.md\n    playbooks:\n      - docs/playbooks/pb1.md\n"
    )
    pb1_content = '---\ntitle: "Playbook 1"\ndescription: "Detailed description"\ntriggers:\n  - "test"\nscope: "exec"\n---\nbody'

    def mock_read(project, rel_path, mode="full"):
        if rel_path == "docs/manuals/role_profiles.yaml":
            return yaml_content
        elif rel_path == "docs/playbooks/pb1.md":
            return pb1_content
        raise Exception("unexpected path")

    with patch("services.playbook_service.read_artifact_logic", side_effect=mock_read):
        res = playbook_service.load("test_proj", "execution")
        assert (
            "- Playbook 1 [docs/playbooks/pb1.md]\n  Detailed description\n  Triggers: test\n  Scope: exec"
            in res
        )


def test_load_returns_stub_without_description_when_field_absent():
    yaml_content = (
        "roles:\n  execution:\n    guideline: g.md\n    playbooks:\n      - docs/playbooks/pb1.md\n"
    )
    pb1_content = '---\ntitle: "Playbook 1"\ntriggers:\n  - "test"\nscope: "exec"\n---\nbody'

    def mock_read(project, rel_path, mode="full"):
        if rel_path == "docs/manuals/role_profiles.yaml":
            return yaml_content
        elif rel_path == "docs/playbooks/pb1.md":
            return pb1_content
        raise Exception("unexpected path")

    with patch("services.playbook_service.read_artifact_logic", side_effect=mock_read):
        res = playbook_service.load("test_proj", "execution")
        assert "- Playbook 1 [docs/playbooks/pb1.md]\n  Triggers: test\n  Scope: exec" in res
        assert "description" not in res


def test_load_returns_path_only_stub_when_frontmatter_missing():
    yaml_content = (
        "roles:\n  execution:\n    guideline: g.md\n    playbooks:\n      - docs/playbooks/pb1.md\n"
    )

    def mock_read(project, rel_path, mode="full"):
        if rel_path == "docs/manuals/role_profiles.yaml":
            return yaml_content
        elif rel_path == "docs/playbooks/pb1.md":
            return "body without frontmatter"
        raise Exception("unexpected path")

    with patch("services.playbook_service.read_artifact_logic", side_effect=mock_read):
        res = playbook_service.load("test_proj", "execution")
        assert "- [docs/playbooks/pb1.md]" in res


def test_load_returns_path_only_stub_when_frontmatter_malformed():
    yaml_content = (
        "roles:\n  execution:\n    guideline: g.md\n    playbooks:\n      - docs/playbooks/pb1.md\n"
    )
    pb1_content = "---\nmalformed yaml : [ : : }\n---\nbody"

    def mock_read(project, rel_path, mode="full"):
        if rel_path == "docs/manuals/role_profiles.yaml":
            return yaml_content
        elif rel_path == "docs/playbooks/pb1.md":
            return pb1_content
        raise Exception("unexpected path")

    with patch("services.playbook_service.read_artifact_logic", side_effect=mock_read):
        res = playbook_service.load("test_proj", "execution")
        assert "- [docs/playbooks/pb1.md]" in res


def test_load_normalizes_display_role_name():
    """load() must accept 'Execution Agent' (raw next_agent_role value) and
    normalise it to 'execution' before the YAML key lookup.  Without
    normalisation this would raise 'Unknown role Execution Agent'."""
    yaml_content = (
        "roles:\n  execution:\n    guideline: g.md\n    playbooks:\n      - skills/pr-review/SKILL.md\n"
    )
    skill_content = '---\ntitle: "PR Review"\ndescription: "Use when opening a PR."\n---\nbody'

    def mock_read(project, rel_path, mode="full"):
        if rel_path == "docs/manuals/role_profiles.yaml":
            return yaml_content
        elif rel_path == "skills/pr-review/SKILL.md":
            return skill_content
        raise Exception("unexpected path")

    with patch("services.playbook_service.read_artifact_logic", side_effect=mock_read):
        res = playbook_service.load("test_proj", "Execution Agent")
        assert "- PR Review [skills/pr-review/SKILL.md]" in res
        assert "Use when opening a PR." in res

