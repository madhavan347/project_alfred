"""Workspace initialization tests."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from alfred.cli.main import main
from alfred.config.initializer import initialize_workspace
from alfred.config.loader import load_config


class WorkspaceInitializerTests(unittest.TestCase):
    def test_initializer_creates_loadable_generic_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = initialize_workspace(root)
            config = load_config(config_path)

            self.assertEqual(config.workspace.root, root.resolve())
            self.assertEqual(config.workspace.repositories, ())
            self.assertEqual(dict(config.agents), {})
            self.assertFalse(config.trackers.markdown.enabled)
            self.assertTrue((root / ".alfred/state").is_dir())
            self.assertTrue((root / ".alfred/tmp").is_dir())

    def test_initializer_refuses_to_replace_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_workspace(root)
            with self.assertRaisesRegex(FileExistsError, "--force"):
                initialize_workspace(root)

    def test_init_command_reports_created_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = StringIO()
            with redirect_stdout(output):
                result = main(["init", "--root", directory])

            self.assertEqual(result, 0)
            self.assertIn("Initialized Alfred workspace", output.getvalue())


if __name__ == "__main__":
    unittest.main()
