"""Command-line entry point: ``alfred-ui`` serves the interface for one Alfred workspace."""

import argparse
import contextlib
import errno
import os
import secrets
import shutil
import socket
import sys
import webbrowser
from collections.abc import Sequence
from pathlib import Path

import uvicorn
from alfred.config.loader import ConfigError

import alfred_ui
from alfred_ui.app import DEFAULT_STATIC, create_app
from alfred_ui.doctor import alfred_directory
from alfred_ui.security import TokenPolicy
from alfred_ui.workspace import WorkspaceContext

DEFAULT_PORT = 8765
PORT_ATTEMPTS = 20


def build_parser() -> argparse.ArgumentParser:
    """Create the ``alfred-ui`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="alfred-ui",
        description="Serve the Alfred web interface for a workspace.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="path to .alfred/config.toml (default: ALFRED_CONFIG, then nearest .alfred/)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="interface to listen on")
    parser.add_argument(
        "--port",
        type=int,
        help=f"port to listen on (default {DEFAULT_PORT}, or the next free one; 0 picks any)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("ALFRED_UI_TOKEN", ""),
        help="access token (default: ALFRED_UI_TOKEN, else a new random token)",
    )
    parser.add_argument(
        "--no-token",
        action="store_true",
        help="disable the access token (only for development on a trusted machine)",
    )
    parser.add_argument("--open", action="store_true", help="open the interface in a browser")
    parser.add_argument(
        "--allow-host",
        action="append",
        default=[],
        help="additional Host header name to accept (repeatable)",
    )
    parser.add_argument(
        "--allow-origin",
        action="append",
        default=[],
        help="additional browser origin to accept, such as a dev server (repeatable)",
    )
    parser.add_argument("--static-dir", type=Path, help="serve a different built frontend")
    parser.add_argument(
        "--log-level",
        default="warning",
        choices=("critical", "error", "warning", "info", "debug"),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {alfred_ui.__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Start the server and block until it is interrupted."""
    args = build_parser().parse_args(argv)
    try:
        context = WorkspaceContext(args.config)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    expose_alfred_to_sessions()
    token = None if args.no_token else (args.token.strip() or secrets.token_urlsafe(24))
    try:
        listener = bind(args.host, args.port)
    except OSError as exc:
        print(f"ERROR: cannot listen on {args.host}: {exc.strerror or exc}", file=sys.stderr)
        return 1
    port = int(listener.getsockname()[1])
    app = create_app(
        context,
        policy=TokenPolicy(token=token, cookie_name=f"alfred_ui_token_{port}"),
        allowed_hosts=tuple(args.allow_host),
        allowed_origins=tuple(args.allow_origin),
        static_directory=args.static_dir or DEFAULT_STATIC,
    )
    url = f"http://{_url_host(args.host)}:{port}/" + (f"?token={token}" if token else "")
    workspace = context.config_path or "no workspace yet (open or create one in Settings)"
    print(f"Alfred UI {alfred_ui.__version__} for {workspace}")
    print(f"Open {url}", flush=True)
    if args.open:
        webbrowser.open(url)
    server = uvicorn.Server(
        uvicorn.Config(app, log_level=args.log_level, access_log=False, lifespan="on")
    )
    # uvicorn re-raises Ctrl-C after shutting down gracefully; stopping is not an error.
    with contextlib.suppress(KeyboardInterrupt):
        server.run(sockets=[listener])
    return 0


def bind(host: str, port: int | None) -> socket.socket:
    """Bind a listening socket, moving past busy ports when none was requested."""
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    candidates = (
        [port] if port is not None else list(range(DEFAULT_PORT, DEFAULT_PORT + PORT_ATTEMPTS))
    )
    error: OSError | None = None
    for candidate in candidates:
        listener = socket.socket(family, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind((host, candidate))
        except OSError as exc:
            listener.close()
            error = exc
            if exc.errno != errno.EADDRINUSE:
                raise
            continue
        return listener
    raise error or OSError(errno.EADDRINUSE, "no free port")


def expose_alfred_to_sessions() -> None:
    """Make this installation's ``alfred`` resolvable in tmux sessions the UI starts.

    Agents report progress by running ``alfred``; a tmux server started by this process inherits
    its PATH, so the directory is appended (never prepended) only when ``alfred`` is missing.
    """
    directory = alfred_directory()
    current = os.environ.get("PATH", "")
    if directory is not None and shutil.which("alfred", path=current) is None:
        os.environ["PATH"] = os.pathsep.join(item for item in (current, str(directory)) if item)


def _url_host(host: str) -> str:
    if host in {"0.0.0.0", "::", ""}:
        return "127.0.0.1"
    return f"[{host}]" if ":" in host else host
