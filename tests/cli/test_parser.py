"""Stable CLI parser tests."""

import unittest

from alfred.cli.parser import build_parser


class ParserTests(unittest.TestCase):
    def test_all_public_resources_parse(self) -> None:
        parser = build_parser()
        commands = {
            "task": ("task", "start", "--task", "1"),
            "agent": ("agent", "status", "--task", "1"),
            "run": ("run", "list"),
            "worktree": ("worktree", "status", "--task", "1"),
            "sync": ("sync", "validate"),
            "knowledge": ("knowledge", "list"),
            "report": ("report", "today"),
            "coordinator": ("coordinator", "status"),
            "learner": ("learner", "status"),
            "notifications": ("notifications",),
        }
        for resource, arguments in commands.items():
            with self.subTest(resource=resource):
                self.assertEqual(parser.parse_args(arguments).resource, resource)

    def test_legacy_completion_aliases_parse(self) -> None:
        args = build_parser().parse_args(
            ("run", "complete", "--task", "7", "--status", "success", "--summary", "Done")
        )
        self.assertEqual(args.status_alias, "success")
        self.assertEqual(args.summary_alias, "Done")


if __name__ == "__main__":
    unittest.main()
