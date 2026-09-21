"""Legacy migration CLI integration test."""

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from alfred.cli.main import main
from alfred.config.initializer import initialize_workspace


class MigrationCommandTests(unittest.TestCase):
    def test_migration_command_reports_backup_and_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = initialize_workspace(root)
            legacy = root / "legacy"
            legacy.mkdir()
            (legacy / "tasks.json").write_text(
                json.dumps(
                    [
                        {
                            "task_number": 7,
                            "title": "Legacy task",
                            "description": "Imported",
                            "worktree_mode": "disabled",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            output = StringIO()
            with redirect_stdout(output):
                code = main(
                    (
                        "--config",
                        str(config),
                        "migrate",
                        "--source",
                        str(legacy),
                    )
                )
            self.assertEqual(code, 0)
            self.assertIn("tasks=1", output.getvalue())
            self.assertIn("Backup:", output.getvalue())
            self.assertTrue((root / ".alfred/migrations/legacy-runtime-v1.json").is_file())


if __name__ == "__main__":
    unittest.main()
