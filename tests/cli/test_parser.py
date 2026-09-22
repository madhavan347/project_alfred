"""Stable CLI parser tests."""

import unittest
from contextlib import redirect_stderr
from io import StringIO

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
            "migrate": ("migrate", "--source", "/tmp/legacy"),
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

    def test_enumerated_options_list_their_valid_values(self) -> None:
        cases = {
            ("run", "list", "--status", "bogus"): r"choose from '?queued'?, '?running",
            ("knowledge", "list", "--category", "bogus"): r"choose from '?patterns'?, '?decisions",
            (
                "knowledge",
                "add",
                "--task",
                "1",
                "--category",
                "bogus",
                "--title",
                "t",
                "--content",
                "c",
            ): r"choose from '?patterns'?, '?decisions",
        }
        for arguments, expected in cases.items():
            with self.subTest(arguments=arguments):
                errors = StringIO()
                with redirect_stderr(errors), self.assertRaises(SystemExit):
                    build_parser().parse_args(arguments)
                self.assertRegex(errors.getvalue(), expected)


if __name__ == "__main__":
    unittest.main()
