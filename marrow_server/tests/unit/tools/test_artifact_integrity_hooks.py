import unittest

from tools.utils.artifact_integrity_hooks import ArtifactIntegrityRegistry, IntegrityHook


class _NoOpHook(IntegrityHook):
    def validate_and_repair(self, project: str, rel_path: str, content: str, mode: str) -> str:
        return content + "_HOOKED"


class TestArtifactIntegrityRegistry(unittest.TestCase):
    def setUp(self):
        # Snapshot the current registry state before each test
        self._snapshot = dict(ArtifactIntegrityRegistry._hooks)

    def tearDown(self):
        # Restore registry to pre-test state
        ArtifactIntegrityRegistry._hooks = self._snapshot

    def test_getHook_unregisteredFilename_returnsNone(self):
        ArtifactIntegrityRegistry._hooks.clear()
        result = ArtifactIntegrityRegistry.get_hook("some_random_file.txt")
        self.assertIsNone(result)

    def test_getHook_registeredFilename_returnsCorrectHook(self):
        hook = _NoOpHook()
        ArtifactIntegrityRegistry.register("myfile.md", hook)
        result = ArtifactIntegrityRegistry.get_hook("myfile.md")
        self.assertIs(result, hook)

    def test_getHook_registeredFilenameUpperCase_isCaseInsensitive(self):
        hook = _NoOpHook()
        ArtifactIntegrityRegistry.register("MyFile.md", hook)
        result = ArtifactIntegrityRegistry.get_hook("MYFILE.MD")
        self.assertIs(result, hook)

    def test_getHook_relPathWithSubdirectory_returnsHookByFilename(self):
        hook = _NoOpHook()
        ArtifactIntegrityRegistry.register("session.md", hook)
        result = ArtifactIntegrityRegistry.get_hook("some/nested/dir/session.md")
        self.assertIs(result, hook)

    def test_register_overwritesSameKey(self):
        hook1 = _NoOpHook()
        hook2 = _NoOpHook()
        ArtifactIntegrityRegistry.register("dupe.md", hook1)
        ArtifactIntegrityRegistry.register("dupe.md", hook2)
        self.assertIs(ArtifactIntegrityRegistry.get_hook("dupe.md"), hook2)


if __name__ == "__main__":
    unittest.main()
