import unittest

from services.role_profile_service import RoleProfile, RoleProfileLoader


class TestRoleProfileLoader(unittest.TestCase):
    def setUp(self):
        self.loader = RoleProfileLoader()
        self.valid_yaml = """
roles:
  discovery:
    guideline: docs/manuals/guidelines/discovery.md
    adrs: ["0007", "0008", "0010", "0011", "0018", "0034"]
    playbooks: []
  architecture:
    guideline: docs/manuals/guidelines/architecture.md
    adrs: ["0007", "0008", "0010", "0011", "0018", "0025"]
    playbooks: []
  planning:
    guideline: docs/manuals/guidelines/planning.md
    adrs: ["0007", "0008", "0010", "0011", "0018", "0035"]
    playbooks: []
  execution:
    guideline: docs/manuals/guidelines/execution.md
    adrs: ["0007", "0008", "0010", "0011", "0018", "0019", "0020", "0025", "0027", "0035"]
    playbooks: []
"""

    def test_load_validYaml_returnsAllRoles(self):
        profiles = self.loader.load(self.valid_yaml)
        self.assertEqual(len(profiles), 4)
        self.assertIn("discovery", profiles)
        self.assertIn("architecture", profiles)
        self.assertIn("planning", profiles)
        self.assertIn("execution", profiles)

    def test_load_missingGuidelineKey_raisesValueError(self):
        invalid_yaml = """
roles:
  discovery:
    adrs: ["0007"]
"""
        with self.assertRaises(ValueError) as ctx:
            self.loader.load(invalid_yaml)
        self.assertIn("discovery", str(ctx.exception))
        self.assertIn("missing required key 'guideline'", str(ctx.exception))

    def test_load_malformedYaml_raisesValueError(self):
        malformed_yaml = """
roles:
  discovery
    guideline: docs/manuals/guidelines/discovery.md
"""
        with self.assertRaises(ValueError) as ctx:
            self.loader.load(malformed_yaml)
        self.assertIn("Malformed role_profiles.yaml", str(ctx.exception))

    def test_load_missingRolesKey_raisesValueError(self):
        missing_roles_yaml = """
discovery:
  guideline: docs/manuals/guidelines/discovery.md
"""
        with self.assertRaises(ValueError) as ctx:
            self.loader.load(missing_roles_yaml)
        self.assertIn("role_profiles.yaml must contain a top-level 'roles' key", str(ctx.exception))

    def test_load_playbooksFieldParsed_returnsEmptyList(self):
        yaml_text = """
roles:
  discovery:
    guideline: docs/manuals/guidelines/discovery.md
    playbooks: []
"""
        profiles = self.loader.load(yaml_text)
        self.assertEqual(profiles["discovery"].playbooks, [])

    def test_load_playbooksFieldAbsent_returnsEmptyList(self):
        yaml_text = """
roles:
  discovery:
    guideline: docs/manuals/guidelines/discovery.md
"""
        profiles = self.loader.load(yaml_text)
        self.assertEqual(profiles["discovery"].playbooks, [])

    def test_getProfile_knownRole_returnsRoleProfile(self):
        profile = self.loader.get_profile(self.valid_yaml, "execution")
        self.assertIsInstance(profile, RoleProfile)
        self.assertEqual(profile.guideline, "docs/manuals/guidelines/execution.md")
        self.assertEqual(
            profile.adrs,
            ["0007", "0008", "0010", "0011", "0018", "0019", "0020", "0025", "0027", "0035"],
        )

    def test_getProfile_unknownRole_returnsErrorString(self):
        error_msg = self.loader.get_profile(self.valid_yaml, "ghost")
        self.assertIsInstance(error_msg, str)
        self.assertIn("Unknown role 'ghost'", error_msg)
        self.assertIn("architecture, discovery, execution, planning", error_msg)

    def test_getProfile_malformedYaml_returnsErrorString(self):
        malformed_yaml = """
roles:
  discovery
    guideline: docs/manuals/guidelines/discovery.md
"""
        error_msg = self.loader.get_profile(malformed_yaml, "discovery")
        self.assertIsInstance(error_msg, str)
        self.assertIn("Malformed role_profiles.yaml", error_msg)

    def test_listRoles_validYaml_returnsAllRoleNames(self):
        roles = self.loader.list_roles(self.valid_yaml)
        self.assertEqual(roles, ["discovery", "architecture", "planning", "execution"])

    def test_listRoles_malformedYaml_returnsEmptyList(self):
        malformed_yaml = """
roles:
  discovery
    guideline: docs/manuals/guidelines/discovery.md
"""
        roles = self.loader.list_roles(malformed_yaml)
        self.assertEqual(roles, [])


    def test_load_nextFieldPresent_parsesNextRole(self):
        yaml_text = """
roles:
  discovery:
    guideline: docs/manuals/guidelines/discovery.md
    next: architecture
    requires_approval: true
"""
        profiles = self.loader.load(yaml_text)
        self.assertEqual(profiles["discovery"].next, "architecture")
        self.assertTrue(profiles["discovery"].requires_approval)

    def test_load_nextFieldAbsent_defaultsToNone(self):
        yaml_text = """
roles:
  reviewer:
    guideline: docs/manuals/guidelines/reviewer.md
"""
        profiles = self.loader.load(yaml_text)
        self.assertIsNone(profiles["reviewer"].next)

    def test_load_nextFieldExplicitNull_parsesAsNone(self):
        yaml_text = """
roles:
  reviewer:
    guideline: docs/manuals/guidelines/reviewer.md
    next: null
"""
        profiles = self.loader.load(yaml_text)
        self.assertIsNone(profiles["reviewer"].next)

    def test_load_requiresApprovalAbsent_defaultsToTrue(self):
        yaml_text = """
roles:
  discovery:
    guideline: docs/manuals/guidelines/discovery.md
    next: architecture
"""
        profiles = self.loader.load(yaml_text)
        self.assertTrue(profiles["discovery"].requires_approval)

    def test_load_requiresApprovalExplicitFalse_parsesAsFalse(self):
        yaml_text = """
roles:
  execution:
    guideline: docs/manuals/guidelines/execution.md
    next: discovery
    requires_approval: false
"""
        profiles = self.loader.load(yaml_text)
        self.assertFalse(profiles["execution"].requires_approval)

    def test_getProfile_knownRole_returnsProfileWithNextAndApproval(self):
        yaml_text = """
roles:
  planning:
    guideline: docs/manuals/guidelines/planning.md
    next: execution
    requires_approval: true
"""
        profile = self.loader.get_profile(yaml_text, "planning")
        self.assertEqual(profile.next, "execution")
        self.assertTrue(profile.requires_approval)


if __name__ == "__main__":
    unittest.main()
