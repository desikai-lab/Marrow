import unittest

from models import ReadRequest


class TestReadRequestModeDefault(unittest.TestCase):
    def test_readRequest_modeOmitted_defaultsToPaged(self):
        req = ReadRequest(path="spec.md")
        self.assertEqual(req.mode, "paged")

    def test_readRequest_modePaged_isAcceptedLiteral(self):
        req = ReadRequest(path="spec.md", mode="paged")
        self.assertEqual(req.mode, "paged")

    def test_readArtifactLogic_defaultMode_isPaged(self):
        import inspect
        from tools.artifacts import read_artifact_logic

        sig = inspect.signature(read_artifact_logic)
        self.assertEqual(sig.parameters["mode"].default, "paged")


class TestFullReadStrategyStrict(unittest.TestCase):
    def setUp(self):
        import os
        import tempfile

        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "big.md")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("x" * 12000)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_FullReadStrategy_ContentExceedsDefaultMaxChars_ReturnsCompleteContent(self):
        from tools.utils.artifact_strategies import FullReadStrategy

        result = FullReadStrategy().read(self.path)
        self.assertEqual(len(result), 12000)
        self.assertNotIn("truncated", result)

    def test_FullReadStrategy_SkipCharsAndDirectionProvided_AreIgnored(self):
        from tools.utils.artifact_strategies import FullReadStrategy

        result = FullReadStrategy().read(self.path, skip_chars=500, direction="end")
        self.assertEqual(len(result), 12000)
        self.assertTrue(result.startswith("x"))


class TestPagedReadStrategy(unittest.TestCase):
    def setUp(self):
        import os
        import tempfile

        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "big.md")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("\n".join(f"line{i}" for i in range(2000)))  # well over 10000 chars

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_PagedReadStrategy_ContentExceedsMaxChars_TruncatesWithMarker(self):
        from tools.utils.artifact_strategies import PagedReadStrategy

        result = PagedReadStrategy().read(self.path)
        self.assertIn("[Text truncated: limit 10000 characters exceeded]", result)

    def test_PagedReadStrategy_DirectionEnd_ReturnsLastMaxCharsWindow(self):
        from tools.utils.artifact_strategies import PagedReadStrategy

        result = PagedReadStrategy().read(self.path, max_chars=50, direction="end")
        with open(self.path, encoding="utf-8") as f:
            full_text = f.read()
        self.assertTrue(full_text.rstrip().endswith(result.strip().splitlines()[-1]))


class TestArtifactStrategyFactoryPaged(unittest.TestCase):
    def test_ArtifactStrategyFactory_PagedMode_ReturnsPagedReadStrategy(self):
        from tools.utils.artifact_strategies import ArtifactStrategyFactory, PagedReadStrategy

        strategy = ArtifactStrategyFactory.get_read_strategy("paged")
        self.assertIsInstance(strategy, PagedReadStrategy)


class TestSectionReadStrategyFull(unittest.TestCase):
    def setUp(self):
        import os
        import tempfile

        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "doc.md")
        section_body = "\n".join(f"detail line {i}" for i in range(600))  # > 10000 chars
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(f"# Intro\nshort\n\n## Target\n{section_body}\n\n## Next\nother\n")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_SectionReadStrategy_SectionExceedsDefaultMaxChars_ReturnsCompleteSection(self):
        from tools.utils.artifact_strategies import SectionReadStrategy

        result = SectionReadStrategy().read(self.path, section_name="Target")
        self.assertIn("detail line 599", result)
        self.assertNotIn("truncated", result)


class TestLinesReadStrategyFull(unittest.TestCase):
    def setUp(self):
        import os
        import tempfile

        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "doc.md")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("\n".join(f"line {i}" for i in range(1, 1501)))  # 1500 lines, > 10000 chars

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_LinesReadStrategy_RangeExceedsDefaultMaxChars_ReturnsCompleteRange(self):
        from tools.utils.artifact_strategies import LinesReadStrategy

        result = LinesReadStrategy().read(self.path, start_line=1, end_line=1500)
        self.assertIn("line 1500", result)
        self.assertNotIn("truncated", result)






