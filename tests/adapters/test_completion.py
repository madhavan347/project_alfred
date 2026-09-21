"""Completion-file handoff tests."""

import tempfile
import unittest
from pathlib import Path

from alfred.adapters.completion import CompletionFileStore
from alfred.domain.constants import CompletionStatus
from alfred.domain.models import CompletionReport


class CompletionFileStoreTests(unittest.TestCase):
    def test_round_trip_and_processed_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = CompletionFileStore(Path(directory))
            report = CompletionReport(
                task_number=7,
                agent="builder",
                status=CompletionStatus.SUCCESS,
                summary="Implemented",
                repositories=("api",),
            )
            path = store.write(report)
            loaded = store.read(path)
            destination = store.mark_processed(path)

            self.assertEqual(loaded, report)
            self.assertFalse(path.exists())
            self.assertTrue(destination.is_file())

    def test_repeated_completions_keep_every_archived_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = CompletionFileStore(Path(directory))
            archived = []
            for summary in ("First attempt", "Second attempt", "Third attempt"):
                report = CompletionReport(
                    task_number=7,
                    agent="builder",
                    status=CompletionStatus.SUCCESS,
                    summary=summary,
                )
                archived.append(store.mark_processed(store.write(report)))
            self.assertEqual(
                [path.name for path in archived],
                ["task-7.json", "task-7-2.json", "task-7-3.json"],
            )
            self.assertEqual(
                [store.read(path).summary for path in archived],
                ["First attempt", "Second attempt", "Third attempt"],
            )
            self.assertEqual(store.pending(), ())

    def test_legacy_failure_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = CompletionFileStore(Path(directory))
            store.pending_directory.mkdir(parents=True)
            path = store.pending_directory / "task-7.json"
            path.write_text(
                '{"task_number": 7, "agent": "builder", "status": "failure", "summary": "Failed"}'
            )
            self.assertEqual(store.read(path).status, CompletionStatus.FAILED)

    def test_invalid_report_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = CompletionFileStore(Path(directory))
            store.pending_directory.mkdir(parents=True)
            path = store.pending_directory / "task-7.json"
            path.write_text("broken")
            with self.assertRaisesRegex(ValueError, "Invalid completion report"):
                store.read(path)


if __name__ == "__main__":
    unittest.main()
