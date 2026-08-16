"""Tmux session backend tests using a recording process runner."""

from pathlib import Path
import tempfile
import unittest

from alfred.adapters.tmux import SessionUnavailable, TmuxSessionBackend
from alfred.ports.process import ProcessResult


class RecordingRunner:
    def __init__(self, results: list[ProcessResult] | None = None) -> None:
        self.calls: list[tuple[tuple[str, ...], Path | None, bool]] = []
        self.results = results or []

    def run(
        self,
        arguments: tuple[str, ...],
        *,
        cwd: Path | None = None,
        check: bool = True,
    ) -> ProcessResult:
        self.calls.append((arguments, cwd, check))
        if self.results:
            return self.results.pop(0)
        return ProcessResult(arguments, 0, "", "")


class TmuxSessionBackendTests(unittest.TestCase):
    def test_unavailable_backend_fails_before_process_execution(self) -> None:
        runner = RecordingRunner()
        backend = TmuxSessionBackend(runner, executable_finder=lambda _: None)
        with self.assertRaisesRegex(SessionUnavailable, "not installed"):
            backend.exists("alfred-task-7")
        self.assertEqual(runner.calls, [])

    def test_create_quotes_command_as_one_tmux_shell_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runner = RecordingRunner()
            backend = TmuxSessionBackend(runner, executable_finder=lambda _: "/usr/bin/tmux")
            backend.create(
                "alfred-task-7",
                Path(directory),
                ("agent-cli", "--message", "text with spaces"),
            )
            arguments = runner.calls[0][0]
            self.assertEqual(arguments[:7], ("tmux", "new-session", "-d", "-s", "alfred-task-7", "-c", directory))
            self.assertEqual(arguments[-1], "agent-cli --message 'text with spaces'")

    def test_prompt_delivery_uses_tmux_buffer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prompt = Path(directory) / "prompt.txt"
            prompt.write_text("Implement the task")
            runner = RecordingRunner()
            backend = TmuxSessionBackend(runner, executable_finder=lambda _: "/usr/bin/tmux")
            backend.send_prompt("alfred-task-7", prompt)
            self.assertEqual(
                [call[0][1] for call in runner.calls],
                ["load-buffer", "paste-buffer", "send-keys"],
            )

    def test_list_filters_prefix_and_handles_missing_server(self) -> None:
        result = ProcessResult(
            ("tmux",),
            0,
            "alfred-task-7\nother\nalfred-task-8\n",
            "",
        )
        backend = TmuxSessionBackend(
            RecordingRunner([result]), executable_finder=lambda _: "/usr/bin/tmux"
        )
        self.assertEqual(backend.list("alfred-task"), ("alfred-task-7", "alfred-task-8"))

    def test_invalid_name_is_rejected(self) -> None:
        backend = TmuxSessionBackend(
            RecordingRunner(), executable_finder=lambda _: "/usr/bin/tmux"
        )
        with self.assertRaisesRegex(ValueError, "Session name"):
            backend.exists("../outside")


if __name__ == "__main__":
    unittest.main()
