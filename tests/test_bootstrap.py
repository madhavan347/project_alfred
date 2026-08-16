"""Application composition tests."""

import tempfile
import unittest
from pathlib import Path

from alfred.adapters.markdown import DisabledTracker
from alfred.bootstrap import build_services
from alfred.config.initializer import initialize_workspace


class BootstrapTests(unittest.TestCase):
    def test_build_services_initializes_state_without_starting_processes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = initialize_workspace(root)
            services = build_services(config_path=config_path)
            self.assertEqual(services.config.workspace.root, root.resolve())
            self.assertEqual(services.store.tasks(), [])
            self.assertIsInstance(services.tasks.tracker, DisabledTracker)
            self.assertFalse(services.learner.marker.exists())


if __name__ == "__main__":
    unittest.main()
