"""Package and entry-point contract tests."""

import subprocess
import sys
import unittest

from alfred import __version__
from alfred.cli.main import main


class PackageContractTests(unittest.TestCase):
    def test_version_is_exposed(self) -> None:
        self.assertEqual(__version__, "0.1.0.dev0")

    def test_main_accepts_empty_arguments(self) -> None:
        self.assertEqual(main([]), 0)

    def test_module_entry_point_reports_version(self) -> None:
        process = subprocess.run(
            [sys.executable, "-m", "alfred", "--version"],
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(process.returncode, 0)
        self.assertEqual(process.stdout.strip(), "alfred 0.1.0.dev0")


if __name__ == "__main__":
    unittest.main()
