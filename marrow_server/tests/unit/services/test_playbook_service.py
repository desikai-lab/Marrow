import unittest

from services.playbook_service import load


class TestPlaybookService(unittest.TestCase):
    def test_load_anyProjectAndRole_returnsEmptyString(self):
        res = load("Proj", "planning")
        self.assertEqual(res, "")
