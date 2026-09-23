"""Bridge a browser terminal to a live tmux session through a pseudo-terminal.

The server runs ``tmux attach-session`` (read-only when requested) inside a PTY and relays bytes
over a WebSocket. It uses ``subprocess`` rather than ``fork`` so no Python code runs in the child
of this multi-threaded server; resizes are applied with ``TIOCSWINSZ`` plus an explicit SIGWINCH.

Client messages are JSON text frames: ``{"type": "input", "data": "..."}`` and
``{"type": "resize", "cols": 120, "rows": 40}``. The server sends raw output as binary frames and
JSON text frames for ``ready``, ``exit``, and ``error`` notices.
"""

import asyncio
import contextlib
import fcntl
import json
import os
import signal
import struct
import subprocess
import termios
import threading
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect

from alfred_ui.tmux_inspector import TmuxInspector, validate_session_name

READ_SIZE = 65536
MIN_SIZE, MAX_COLS, MAX_ROWS = 2, 500, 200


class TerminalBridge:
    """Serve interactive or read-only terminals attached to tmux sessions."""

    def __init__(self, inspector: TmuxInspector) -> None:
        self.inspector = inspector
        self.processes: set[subprocess.Popen[bytes]] = set()

    async def serve(
        self,
        websocket: WebSocket,
        session_name: str,
        *,
        readonly: bool,
        cols: int,
        rows: int,
    ) -> None:
        """Attach to ``session_name`` until either side disconnects."""
        await websocket.accept()
        try:
            validate_session_name(session_name)
        except ValueError as exc:
            await _notice_and_close(websocket, "error", str(exc))
            return
        if not self.inspector.available():
            await _notice_and_close(websocket, "error", "tmux is not available on PATH")
            return
        if not await asyncio.to_thread(self.inspector.exists, session_name):
            await _notice_and_close(websocket, "error", f"Session {session_name} is not running")
            return

        master, slave = os.openpty()
        _set_size(slave, _clamp(rows, MAX_ROWS, 24), _clamp(cols, MAX_COLS, 80))
        environment = dict(os.environ)
        environment.pop("TMUX", None)
        environment["TERM"] = "xterm-256color"
        arguments = ["tmux", "-u", "attach-session"]
        if readonly:
            arguments.append("-r")
        arguments.extend(["-t", f"={session_name}"])
        process = subprocess.Popen(
            arguments,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=environment,
            start_new_session=True,
            close_fds=True,
        )
        os.close(slave)
        os.set_blocking(master, False)
        self.processes.add(process)
        loop = asyncio.get_running_loop()
        output: asyncio.Queue[bytes | None] = asyncio.Queue()

        def readable() -> None:
            try:
                data = os.read(master, READ_SIZE)
            except BlockingIOError:
                return
            except OSError:
                data = b""
            if not data:
                loop.remove_reader(master)
                output.put_nowait(None)
                return
            output.put_nowait(data)

        loop.add_reader(master, readable)
        await websocket.send_text(json.dumps({"type": "ready", "session": session_name}))
        pump_out = asyncio.create_task(_pump_output(websocket, output))
        pump_in = asyncio.create_task(_pump_input(websocket, master, process))
        try:
            await asyncio.wait({pump_out, pump_in}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            # Release everything synchronously first so a cancelled handler cannot leak the
            # descriptor or leave the tmux client attached; reap the process off the loop.
            for task in (pump_out, pump_in):
                task.cancel()
            loop.remove_reader(master)
            with contextlib.suppress(ProcessLookupError):
                process.terminate()
            with contextlib.suppress(OSError):
                os.close(master)
            self.processes.discard(process)
            threading.Thread(target=_terminate, args=(process,), daemon=True).start()
            with contextlib.suppress(Exception):
                await websocket.close()

    def close_all(self) -> None:
        """Detach every terminal client (used at shutdown)."""
        for process in list(self.processes):
            _terminate(process)
        self.processes.clear()


async def _pump_output(websocket: WebSocket, output: "asyncio.Queue[bytes | None]") -> None:
    while True:
        chunk = await output.get()
        if chunk is None:
            break
        parts = [chunk]
        ended = False
        # Coalesce bursts so a redraw becomes one frame instead of hundreds.
        await asyncio.sleep(0.004)
        while not output.empty():
            item = output.get_nowait()
            if item is None:
                ended = True
                break
            parts.append(item)
        await websocket.send_bytes(b"".join(parts))
        if ended:
            break
    with contextlib.suppress(Exception):
        await websocket.send_text(json.dumps({"type": "exit"}))


async def _pump_input(
    websocket: WebSocket, master: int, process: "subprocess.Popen[bytes]"
) -> None:
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message.get("bytes") is not None:
                await _write(master, message["bytes"])
                continue
            text = message.get("text")
            if text is None:
                continue
            try:
                request: Any = json.loads(text)
            except ValueError:
                continue
            if not isinstance(request, dict):
                continue
            if request.get("type") == "input" and isinstance(request.get("data"), str):
                await _write(master, request["data"].encode("utf-8"))
            elif request.get("type") == "resize":
                cols = _clamp(_integer(request.get("cols")), MAX_COLS, 80)
                rows = _clamp(_integer(request.get("rows")), MAX_ROWS, 24)
                _set_size(master, rows, cols)
                with contextlib.suppress(ProcessLookupError):
                    os.kill(process.pid, signal.SIGWINCH)
    except WebSocketDisconnect:
        return


async def _write(master: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        try:
            written = os.write(master, view)
        except BlockingIOError:
            await asyncio.sleep(0.005)
            continue
        except OSError:
            return
        view = view[written:]


async def _notice_and_close(websocket: WebSocket, kind: str, message: str) -> None:
    with contextlib.suppress(Exception):
        await websocket.send_text(json.dumps({"type": kind, "message": message}))
        await websocket.close(code=4000)


def _set_size(descriptor: int, rows: int, cols: int) -> None:
    with contextlib.suppress(OSError):
        fcntl.ioctl(descriptor, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def _terminate(process: "subprocess.Popen[bytes]") -> None:
    if process.poll() is not None:
        return
    with contextlib.suppress(ProcessLookupError):
        process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=2)


def _integer(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _clamp(value: int, maximum: int, default: int) -> int:
    return max(MIN_SIZE, min(maximum, value or default))
