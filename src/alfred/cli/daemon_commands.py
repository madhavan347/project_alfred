"""Coordinator and learner session command handlers."""

import argparse
import signal
import sys
from threading import Event

from alfred.bootstrap import AlfredServices


def handle_coordinator(args: argparse.Namespace, services: AlfredServices) -> int:
    """Start, stop, inspect, or directly run the completion coordinator."""
    action = args.action or "status"
    name = f"{services.config.runtime.session_prefix}-coordinator"
    if action == "start":
        if not services.sessions.available():
            raise RuntimeError("tmux is required to start the coordinator in the background")
        if services.sessions.exists(name):
            print(f"Coordinator already running: {name}")
            return 0
        command = (
            sys.executable,
            "-m",
            "alfred",
            "--config",
            str(services.config.config_path),
            "coordinator",
            "loop",
        )
        services.sessions.create(name, services.config.workspace.root, command)
        print(f"Coordinator started: {name}")
        return 0
    if action == "stop":
        if services.sessions.available() and services.sessions.exists(name):
            services.sessions.stop(name)
            print(f"Coordinator stopped: {name}")
        else:
            print("Coordinator is not running")
        return 0
    if action == "once":
        cycle = services.coordinator.process_once()
        print(
            f"Processed={cycle.processed} invalid={cycle.invalid} "
            f"dead_sessions={cycle.dead_sessions}"
        )
        return 0
    if action == "loop":
        stop = Event()
        signal.signal(signal.SIGINT, lambda _signum, _frame: stop.set())
        signal.signal(signal.SIGTERM, lambda _signum, _frame: stop.set())
        services.coordinator.run(stop)
        return 0
    if action == "status":
        running = services.sessions.available() and services.sessions.exists(name)
        print(f"Coordinator: {'running' if running else 'stopped'}")
        if running:
            print(f"Session: {name}")
        return 0
    raise ValueError(f"Unsupported coordinator action: {action}")


def handle_learner(args: argparse.Namespace, services: AlfredServices) -> int:
    """Start, stop, inspect, or attach to the configured learner agent."""
    action = args.action or "status"
    if action == "start":
        alias = args.agent or next(iter(sorted(services.config.agents)), "")
        if not alias:
            raise ValueError("Configure an agent or pass --agent")
        started = services.learner.start(alias)
        print("Learner started" if started else "Learner already running")
        return 0
    if action == "stop":
        stopped = services.learner.stop()
        print("Learner stopped" if stopped else "Learner is not running")
        return 0
    status = services.learner.status()
    if action == "attach":
        if not status.running:
            raise ValueError("Learner is not running")
        print(f"tmux attach-session -t {status.session_name}")
        return 0
    if action == "status":
        print(f"Learner: {'running' if status.running else 'stopped'}")
        print(f"Session: {status.session_name}")
        if status.agent_alias:
            print(f"Agent: {status.agent_alias}")
        return 0
    raise ValueError(f"Unsupported learner action: {action}")
