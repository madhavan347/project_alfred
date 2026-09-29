"""Describe configured agents: which CLI and model each command runs, and how prompts arrive."""

from collections.abc import Sequence
from pathlib import PurePath
from string import Formatter
from typing import Any

from alfred.config.models import AgentConfig

KNOWN_CLIS = {
    "claude": "Claude Code",
    "codex": "Codex CLI",
    "agy": "Antigravity",
    "gemini": "Gemini CLI",
    "aider": "Aider",
    "cursor-agent": "Cursor Agent",
    "opencode": "OpenCode",
    "amp": "Amp",
    "goose": "Goose",
    "qwen": "Qwen Code",
    "copilot": "GitHub Copilot CLI",
    "tail": "tail (test recorder)",
}
PROMPT_PLACEHOLDERS = frozenset({"prompt", "prompt_file"})
TASK_PLACEHOLDERS = frozenset(
    {"task_number", "task_title", "task_branch", "phase", "workdir", *PROMPT_PLACEHOLDERS}
)


def describe_agent(agent: AgentConfig) -> dict[str, Any]:
    """Return a JSON-friendly description of one configured agent."""
    commands = {
        "direct": list(agent.commands.direct),
        "plan": list(agent.commands.plan),
        "execution": list(agent.commands.execution),
    }
    execution = agent.commands.execution
    executable = PurePath(execution[0]).name if execution else ""
    return {
        "alias": agent.alias,
        "runtime_target": agent.runtime_target,
        "commands": commands,
        "executable": executable,
        "cli": cli_label(execution),
        "model": detect_model(execution) or detect_model(agent.commands.plan),
        "prompt_delivery": {
            phase: "argument" if delivers_prompt(command) else "paste"
            for phase, command in commands.items()
        },
        "placeholders": {
            phase: sorted(placeholders(command)) for phase, command in commands.items()
        },
        "unknown_placeholders": {
            phase: sorted(placeholders(command) - TASK_PLACEHOLDERS)
            for phase, command in commands.items()
            if phase != "direct" and placeholders(command) - TASK_PLACEHOLDERS
        },
    }


def cli_label(command: Sequence[str]) -> str:
    """Return a friendly product name for a command's executable."""
    if not command:
        return ""
    executable = PurePath(command[0]).name
    if executable in {"python", "python3"} or executable.startswith("python3."):
        script = next((PurePath(item).name for item in command[1:] if item.endswith(".py")), "")
        return f"Python script ({script})" if script else "Python"
    return KNOWN_CLIS.get(executable, executable)


def detect_model(command: Sequence[str]) -> str:
    """Return a model named by ``--model``, ``-m``, or ``-c model=...`` arguments."""
    arguments = list(command)
    for index, argument in enumerate(arguments):
        following = arguments[index + 1] if index + 1 < len(arguments) else ""
        if argument in {"--model", "-m"} and following:
            return following
        if argument.startswith("--model="):
            return argument.split("=", 1)[1]
        if argument in {"-c", "--config"} and following.startswith("model="):
            return following.split("=", 1)[1].strip("\"'")
    return ""


def placeholders(command: Sequence[str]) -> set[str]:
    """Return the format placeholders used by a command template."""
    found: set[str] = set()
    for argument in command:
        try:
            parsed = list(Formatter().parse(argument))
        except ValueError:
            continue
        found.update(field for _, field, _, _ in parsed if field)
    return found


def delivers_prompt(command: Sequence[str]) -> bool:
    """Return whether the command passes the prompt itself instead of relying on paste."""
    return bool(placeholders(command) & PROMPT_PLACEHOLDERS)
