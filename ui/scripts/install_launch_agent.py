"""Install and start the local Alfred UI as a macOS LaunchAgent."""

import os
import plistlib
import subprocess
from pathlib import Path

LABEL = "com.shriram.alfred-ui"
PORT = "8765"
ROOT = Path(__file__).resolve().parents[2]
SERVICE_DIR = ROOT / ".alfred" / "ui-service"
AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def main() -> None:
    """Write the service definition and load it into the current login session."""
    executable = ROOT / "ui" / ".venv" / "bin" / "alfred-ui"
    config = ROOT / ".alfred" / "config.toml"
    if not executable.is_file() or not config.is_file():
        raise SystemExit("Install the UI and initialize .alfred/config.toml first")

    SERVICE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(SERVICE_DIR, 0o700)
    for name in ("stdout.log", "stderr.log"):
        path = SERVICE_DIR / name
        path.touch(mode=0o600, exist_ok=True)
        os.chmod(path, 0o600)

    agent = {
        "Label": LABEL,
        "ProgramArguments": [
            str(executable),
            "--config",
            str(config),
            "--host",
            "127.0.0.1",
            "--port",
            PORT,
            "--no-token",
        ],
        "WorkingDirectory": str(ROOT),
        "EnvironmentVariables": {
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        },
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(SERVICE_DIR / "stdout.log"),
        "StandardErrorPath": str(SERVICE_DIR / "stderr.log"),
    }
    AGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AGENT_PATH.open("wb") as file:
        plistlib.dump(agent, file)

    service = f"gui/{os.getuid()}/{LABEL}"
    subprocess.run(
        ["launchctl", "bootout", service],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(AGENT_PATH)],
        check=True,
    )
    print(f"Alfred UI service started at http://127.0.0.1:{PORT}/")


if __name__ == "__main__":
    main()
