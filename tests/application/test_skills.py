"""Editable plan and execution skill tests."""

import tempfile
import unittest
from pathlib import Path

from alfred.application.skills import MAX_SKILL_BYTES, SkillService
from alfred.domain.constants import PromptPhase


class SkillServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.service = SkillService(Path(self.temporary.name) / "skills")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_set_get_and_remove_round_trip(self) -> None:
        self.assertEqual(self.service.get(PromptPhase.PLAN), "")
        path = self.service.set("plan", "  Always list risks.  ")
        self.assertEqual(path.name, "plan.md")
        self.assertEqual(self.service.get(PromptPhase.PLAN), "Always list risks.")
        self.assertTrue(self.service.remove("plan"))
        self.assertFalse(self.service.remove("plan"))

    def test_rejects_unknown_phase_empty_and_oversized_content(self) -> None:
        with self.assertRaises(ValueError):
            self.service.path("deploy")
        with self.assertRaisesRegex(ValueError, "empty"):
            self.service.set("plan", "  ")
        with self.assertRaisesRegex(ValueError, "at most"):
            self.service.set("execution", "x" * (MAX_SKILL_BYTES + 1))
