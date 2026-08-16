"""Configuration detail-object tests."""

from pathlib import Path
import unittest

from alfred.config.constants import DEFAULT_COMMIT_TAGS
from alfred.config.models import AlfredConfig, RepositoryConfig, WorkspaceConfig


class ConfigModelTests(unittest.TestCase):
    def test_defaults_are_generic_and_immutable(self) -> None:
        config = AlfredConfig(
            config_path=Path("/workspace/.alfred/config.toml"),
            workspace=WorkspaceConfig(root=Path("/workspace")),
        )

        self.assertEqual(config.runtime.timezone, "UTC")
        self.assertFalse(config.trackers.markdown.enabled)
        self.assertEqual(dict(config.commits.tags), DEFAULT_COMMIT_TAGS)

        with self.assertRaises(TypeError):
            config.commits.tags["OTHER"] = "[OTHER]"  # type: ignore[index]

    def test_repository_lookup_is_explicit(self) -> None:
        repository = RepositoryConfig(name="api", path=Path("/workspace/api"))
        workspace = WorkspaceConfig(root=Path("/workspace"), repositories=(repository,))

        self.assertIs(workspace.repository("api"), repository)
        with self.assertRaisesRegex(KeyError, "configured repositories: api"):
            workspace.repository("missing")


if __name__ == "__main__":
    unittest.main()
