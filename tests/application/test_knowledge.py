"""Markdown knowledge-store tests."""

from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from alfred.application.knowledge import KnowledgeService
from alfred.utils.text import slugify
from alfred.utils.time import Clock


class FixedClock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 8, 16, 10, 30, tzinfo=ZoneInfo("UTC"))


class KnowledgeServiceTests(unittest.TestCase):
    def test_add_list_and_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = KnowledgeService(Path(directory), FixedClock(ZoneInfo("UTC")))
            path = service.add(
                7,
                "patterns",
                "Atomic state writes",
                "Write temporary files beside their targets.",
                agent="builder",
                related_repositories=("api",),
            )
            self.assertTrue(path.is_file())
            self.assertEqual(service.list("patterns"), (path,))
            self.assertEqual(service.count_for_task(7), 1)
            self.assertIn("Repositories: api", path.read_text())

    def test_duplicate_filename_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = KnowledgeService(Path(directory), FixedClock(ZoneInfo("UTC")))
            service.add(7, "patterns", "Example", "First")
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                service.add(7, "patterns", "Example", "Second")

    def test_slugify_has_stable_empty_fallback(self) -> None:
        self.assertEqual(slugify("Symbols !!!"), "symbols")
        self.assertEqual(slugify("!!!"), "entry")


if __name__ == "__main__":
    unittest.main()
