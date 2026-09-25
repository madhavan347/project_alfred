"""TOML configuration discovery and loading tests."""

import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from alfred.config.loader import ConfigError, discover_config, load_config

VALID_CONFIG = """
version = 1

[alfred]
timezone = "Europe/London"
state_directory = ".alfred/state"
temp_directory = ".alfred/tmp"
worktree_directory = ".alfred/worktrees"
session_prefix = "workflow"
tmux_unavailable_policy = "error"

[workspace]
root = ".."

[[repositories]]
name = "api"
path = "repos/api"
default_branch = "trunk"
selected_by_default = true

[agents.builder]
runtime_target = "local-cli"

[agents.builder.commands]
direct = ["local-cli"]
plan = ["local-cli", "--plan"]
execution = ["local-cli", "--execute"]

[trackers.markdown]
enabled = true
canonical = "notes/tasks.md"
agents = "notes/agents.md"
daily_notes = "notes/daily"

[commit.tags]
patch = "[PATCH]"
fix = "[FIX]"

[knowledge]
directory = ".alfred/knowledge"
required_completion_entries = 1
"""


class ConfigLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config_directory = self.root / ".alfred"
        self.config_directory.mkdir()
        self.config_path = self.config_directory / "config.toml"
        self.config_path.write_text(textwrap.dedent(VALID_CONFIG), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_loads_and_resolves_typed_configuration(self) -> None:
        config = load_config(self.config_path)

        self.assertEqual(config.workspace.root, self.root.resolve())
        self.assertEqual(
            config.workspace.repository("api").path,
            (self.root / "repos/api").resolve(),
        )
        self.assertEqual(config.runtime.timezone, "Europe/London")
        self.assertEqual(config.agents["builder"].commands.plan, ("local-cli", "--plan"))
        self.assertTrue(config.trackers.markdown.enabled)
        self.assertEqual(config.commits.tags["PATCH"], "[PATCH]")
        self.assertEqual(config.knowledge.required_completion_entries, 1)

    def test_discovery_walks_parent_directories(self) -> None:
        nested = self.root / "repos" / "api"
        nested.mkdir(parents=True)
        self.assertEqual(discover_config(nested), self.config_path.resolve())

    def test_explicit_path_precedes_environment(self) -> None:
        with patch.dict(os.environ, {"ALFRED_CONFIG": "/missing/config.toml"}):
            self.assertEqual(discover_config(explicit=self.config_path), self.config_path.resolve())

    def test_unknown_keys_are_rejected(self) -> None:
        self.config_path.write_text("version = 1\nunexpected = true\n", encoding="utf-8")
        with self.assertRaisesRegex(ConfigError, "Unknown keys"):
            load_config(self.config_path)

    def test_enabled_tracker_requires_all_paths(self) -> None:
        self.config_path.write_text(
            "version = 1\n[trackers.markdown]\nenabled = true\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigError, "requires canonical"):
            load_config(self.config_path)

    def test_invalid_session_prefix_is_rejected_at_load(self) -> None:
        config = VALID_CONFIG.replace(
            'session_prefix = "workflow"', 'session_prefix = "bad prefix"'
        )
        self.config_path.write_text(textwrap.dedent(config), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Session prefix must start with an alphanumeric"):
            load_config(self.config_path)

    def test_unsafe_repository_git_names_are_rejected_at_load(self) -> None:
        replacements = {
            'default_branch = "trunk"': 'default_branch = "-trunk"',
            "selected_by_default = true": 'remote = "bad remote"\nselected_by_default = true',
        }
        for old, new in replacements.items():
            with self.subTest(new=new):
                config = VALID_CONFIG.replace(old, new, 1)
                self.config_path.write_text(textwrap.dedent(config), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Repository api (default_branch|remote)"):
                    load_config(self.config_path)

    def test_invalid_toml_has_actionable_error(self) -> None:
        self.config_path.write_text("[broken", encoding="utf-8")
        with self.assertRaisesRegex(ConfigError, "Invalid TOML"):
            load_config(self.config_path)


if __name__ == "__main__":
    unittest.main()
