#!/usr/bin/env python3
"""A scripted stand-in for a coding agent, used to exercise Alfred and its UI end to end.

It behaves like an interactive agent CLI inside a tmux session: it reads the prompt Alfred
rendered, reports through the real ``alfred`` command (found on PATH, exactly like a real agent),
edits files in its worktree, and then waits for further prompts pasted into the session.

Markers in the task description change its behavior:

    [fake:trust]      ask "Do you trust this folder? (y/n)" and wait for an answer
    [fake:wait]       wait for the operator to type "go" before completing
    [fake:fail]       report a failed completion
    [fake:fail-once]  fail the first execution attempt, succeed when reopened
    [fake:block]      report a blocked completion
    [fake:exit]       exit right after starting, so the session dies
    [fake:commit]     commit its change instead of leaving it for the operator
    [fake:noknowledge] skip the knowledge entry
"""

import argparse
import os
import re
import select
import shutil
import subprocess
import sys
import time
from pathlib import Path

BOLD, DIM, GREEN, YELLOW, RED, CYAN, RESET = (
    "\033[1m",
    "\033[2m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
    "\033[36m",
    "\033[0m",
)


def say(text: str = "", color: str = "") -> None:
    """Print one line, flushed so tmux shows it immediately."""
    print(f"{color}{text}{RESET if color else ''}", flush=True)


def pause(seconds: float) -> None:
    """Sleep briefly so progress is visible in a live view."""
    time.sleep(seconds)


def alfred(*arguments: str) -> bool:
    """Run the real alfred CLI and show its output in the session."""
    executable = shutil.which("alfred")
    if executable is None:
        say("alfred is not on PATH, so this agent cannot report to Alfred.", RED)
        return False
    say(f"$ alfred {' '.join(_quote(item) for item in arguments)}", DIM)
    result = subprocess.run([executable, *arguments], capture_output=True, text=True, check=False)
    output = (result.stdout + result.stderr).strip()
    if output:
        say(output, GREEN if result.returncode == 0 else RED)
    return result.returncode == 0


def _quote(value: str) -> str:
    return value if re.fullmatch(r"[\w@%+=:,./-]+", value) else repr(value)


def read_line(prompt: str = "") -> str:
    """Read one line from the terminal."""
    if prompt:
        sys.stdout.write(prompt)
        sys.stdout.flush()
    line = sys.stdin.readline()
    if not line:
        raise SystemExit(0)
    return line.rstrip("\n")


def drain(seconds: float = 1.0) -> list[str]:
    """Collect every line that arrives within a short quiet period (the rest of a paste)."""
    lines: list[str] = []
    deadline = time.monotonic() + seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return lines
        ready, _, _ = select.select([sys.stdin], [], [], remaining)
        if not ready:
            return lines
        line = sys.stdin.readline()
        if not line:
            return lines
        lines.append(line.rstrip("\n"))
        deadline = time.monotonic() + 0.4


class Agent:
    """One simulated agent session."""

    def __init__(self, alias: str, task: int) -> None:
        self.alias = alias
        self.task = task
        self.actor = f"agent:{alias}"
        self.attempts = 0

    def run(self, phase: str, prompt: str) -> None:
        """Handle the prompt this session was started with, then keep listening."""
        say(f"{BOLD}{CYAN}Fake agent {self.alias}{RESET} working on task {self.task}")
        say(f"Phase: {phase}", DIM)
        say("")
        for line in prompt.splitlines():
            say(f"  {line}", DIM)
        say("")
        markers = set(re.findall(r"\[fake:([a-z-]+)\]", prompt))
        if "exit" in markers:
            say("Simulating a crash: exiting now.", RED)
            raise SystemExit(3)
        if "trust" in markers:
            answer = read_line(f"{YELLOW}Do you trust the files in this folder? (y/n) {RESET}")
            if answer.strip().lower() not in {"y", "yes"}:
                say("Not trusted. Exiting.", RED)
                raise SystemExit(4)
            say("Folder trusted.", GREEN)
        if phase == "plan":
            self.plan(prompt)
        else:
            self.execute(prompt)
        self.listen()

    def plan(self, prompt: str) -> None:
        """Write a plan and report it with ``alfred run event --type plan_completed``."""
        title = _field(prompt, r"^# Task \d+: (.*)$") or "the task"
        say(f"{BOLD}Planning {title}{RESET}")
        pause(0.8)
        steps = [
            "Read the task description and the repository layout.",
            "Add the change in a new file next to the existing code.",
            "Record what was learned as a knowledge entry.",
            "Validate the change and report completion.",
        ]
        plan = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
        say("## Plan")
        for line in plan.splitlines():
            say(line)
            pause(0.2)
        alfred(
            "run",
            "event",
            "--task",
            str(self.task),
            "--type",
            "plan_completed",
            "--note",
            f"Plan for {title}:\n{plan}",
            "--actor",
            self.actor,
        )
        say("Waiting for plan approval.", YELLOW)

    def execute(self, prompt: str) -> None:
        """Change a file in the worktree, add knowledge, and report completion."""
        self.attempts += 1
        markers = set(re.findall(r"\[fake:([a-z-]+)\]", prompt))
        workdir = _worktree(prompt) or Path.cwd()
        say(f"{BOLD}Executing in {workdir}{RESET} (attempt {self.attempts})")
        alfred(
            "task",
            "progress",
            "--task",
            str(self.task),
            "--note",
            f"{self.alias} started implementing (attempt {self.attempts})",
            "--actor",
            self.actor,
        )
        pause(0.6)
        target = workdir / f"fake-agent-task-{self.task}.txt"
        target.write_text(
            f"Change for task {self.task} by {self.alias}, attempt {self.attempts}.\n",
            encoding="utf-8",
        )
        say(f"Wrote {target.name}", GREEN)
        if "commit" in markers:
            subprocess.run(["git", "add", "-A"], cwd=workdir, check=False)
            subprocess.run(
                ["git", "commit", "-m", f"Task {self.task} change by {self.alias}"],
                cwd=workdir,
                check=False,
                capture_output=True,
            )
            say("Committed the change.", GREEN)
        if "noknowledge" not in markers:
            alfred(
                "knowledge",
                "add",
                "--task",
                str(self.task),
                "--category",
                "patterns",
                "--title",
                f"Task {self.task} attempt {self.attempts} by {self.alias}",
                "--content",
                "Fake agents write one file per task and report through the alfred CLI.",
                "--agent",
                self.alias,
            )
        if "wait" in markers:
            while read_line(f"{YELLOW}Type go and press Enter to finish: {RESET}").strip() != "go":
                say("Waiting for go.", DIM)
        if "block" in markers:
            result, note = "blocked", "Blocked: the test fixture is unavailable."
        elif "fail" in markers or ("fail-once" in markers and self.attempts == 1):
            result, note = "failed", f"Attempt {self.attempts} failed its checks."
        else:
            result, note = "success", f"Implemented task {self.task} in {target.name}."
        alfred(
            "run",
            "complete",
            "--task",
            str(self.task),
            "--result",
            result,
            "--note",
            note,
            "--actor",
            self.actor,
        )
        say(f"Reported {result}.", GREEN if result == "success" else YELLOW)

    def listen(self) -> None:
        """Wait for more prompts, as an interactive agent would."""
        say("Ready for further instructions.", DIM)
        while True:
            line = read_line()
            lines = [line, *drain(0.8)]
            text = "\n".join(lines)
            if "## Phase: EXECUTION" in text:
                say("Received an execution prompt.", CYAN)
                self.execute(text)
            elif "## Phase: PLAN" in text:
                self.plan(text)
            elif text.strip():
                say(f"Operator: {text.strip()}", CYAN)
            say("Ready for further instructions.", DIM)


def _field(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _worktree(prompt: str) -> Path | None:
    """Return the first worktree path listed under 'Working directories'."""
    section = prompt.split("## Working directories", 1)
    if len(section) < 2:
        return None
    for line in section[1].splitlines():
        match = re.match(r"- ([^:(]+?)(?: \([^)]*\))?: (/.+)$", line.strip())
        if match and match.group(1) != "workspace":
            path = Path(match.group(2))
            if path.is_dir() and "/worktrees/" in str(path):
                return path
    return None


def main() -> int:
    """Parse arguments and run the agent."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=("plan", "execution", "direct"))
    parser.add_argument("--task", type=int, default=0)
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--agent", default=os.environ.get("FAKE_AGENT_ALIAS", "fake"))
    args = parser.parse_args()
    prompt = args.prompt_file.read_text(encoding="utf-8") if args.prompt_file else ""
    task = args.task or int(_field(prompt, r"^# Task (\d+):") or 0)
    agent = Agent(_field(prompt, r"^Agent: (\S+)") or args.agent, task)
    if args.phase == "direct":
        say(f"{BOLD}Fake learner ready{RESET}")
        for line in prompt.splitlines():
            say(f"  {line}", DIM)
        agent.listen()
        return 0
    try:
        agent.run(args.phase, prompt)
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
