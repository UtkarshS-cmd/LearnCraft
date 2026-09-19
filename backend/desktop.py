"""Run LearnCraft as a desktop application.

The launcher keeps the Flask server local to this machine and opens the
existing web UI in an app-style Edge/Chrome window when available. It has no
extra runtime dependency, so it works with the repository's Python setup.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from threading import Thread
from urllib.request import urlopen

from werkzeug.serving import make_server

from app.main import create_app


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _open_app_window(url: str) -> subprocess.Popen | None:
    browsers = (
        ("msedge", "--app="),
        ("chrome", "--app="),
        ("msedge.exe", "--app="),
        ("chrome.exe", "--app="),
    )
    for executable, flag in browsers:
        path = shutil.which(executable)
        if path:
            return subprocess.Popen([path, f"{flag}{url}"], close_fds=True)
    webbrowser.open(url)
    return None


def run_desktop(port: int | None = None, open_window: bool = True) -> None:
    """Start the local server and keep it alive until interrupted."""
    os.environ.setdefault("LEARNCRAFT_NETWORK_MODE", "OFFLINE")
    selected_port = port or _free_port()
    server = make_server("127.0.0.1", selected_port, create_app(), threaded=True)
    thread = Thread(target=server.serve_forever, name="learncraft-server", daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{selected_port}/login"

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=0.5):
                break
        except OSError:
            time.sleep(0.1)
    else:
        server.shutdown()
        raise RuntimeError(f"LearnCraft server did not become ready at {url}.")

    print(f"LearnCraft desktop app is running at {url}")
    if open_window:
        _open_app_window(url)
    try:
        while thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping LearnCraft...")
    finally:
        server.shutdown()
        thread.join(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LearnCraft in a desktop browser window.")
    parser.add_argument("--port", type=int, help="Local port (defaults to an available port).")
    parser.add_argument("--no-window", action="store_true", help="Start the local server without opening a browser.")
    args = parser.parse_args()
    run_desktop(port=args.port, open_window=not args.no_window)


if __name__ == "__main__":
    main()
