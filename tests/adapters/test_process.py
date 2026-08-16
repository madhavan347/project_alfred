"""Structured subprocess adapter tests."""

import sys
import tempfile
import unittest
from pathlib import Path

from alfred.adapters.process import ProcessError, SubprocessRunner


class SubprocessRunnerTests(unittest.TestCase):
    def test_captures_output_without_a_shell(self) -> None:
        result = SubprocessRunner().run(
            (sys.executable, "-c", "print('hello')"),
            check=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "hello")

    def test_preserves_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = SubprocessRunner().run(
                (sys.executable, "-c", "from pathlib import Path; print(Path.cwd())"),
                cwd=Path(directory),
            )
            self.assertEqual(Path(result.stdout.strip()).resolve(), Path(directory).resolve())

    def test_checked_failure_has_actionable_context(self) -> None:
        with self.assertRaisesRegex(ProcessError, "status 4") as raised:
            SubprocessRunner().run((sys.executable, "-c", "raise SystemExit(4)"))
        self.assertEqual(raised.exception.result.returncode, 4)

    def test_unchecked_failure_is_returned(self) -> None:
        result = SubprocessRunner().run(
            (sys.executable, "-c", "raise SystemExit(3)"),
            check=False,
        )
        self.assertEqual(result.returncode, 3)


if __name__ == "__main__":
    unittest.main()
