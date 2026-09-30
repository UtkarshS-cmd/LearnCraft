"""Share LearnCraft online with one command (phone / multiple devices).

Starts the local LearnCraft server and exposes it through a public HTTPS
tunnel, so any phone or tablet can open it from anywhere — no router port
forwarding, no static IP, no VPS.

Tunnel providers (auto-detected in this order):

  1. ``cloudflared``  - free, no account: gives https://<random>.trycloudflare.com
                        install: winget install --id Cloudflare.cloudflared
  2. ``ngrok``        - free account: https://<random>.ngrok-free.app
                        install: winget install ngrok.ngrok
                        once   : ngrok config add-authtoken <token>
  3. ``ssh``          - already installed on Windows 10+/macOS/Linux; uses the
                        free localhost.run relay: https://<random>.lhr.life

Usage::

    python scripts/share_online.py                 # auto tool, port 5000
    python scripts/share_online.py --port 8080
    python scripts/share_online.py --tool ssh      # no install needed
    python scripts/share_online.py --no-qr         # narrow terminals
    python scripts/share_online.py --local-only    # tunnel only, no LAN bind

The same thing is wired into the repo runners::

    run_server.bat share            (Windows cmd)
    .\\run_server.ps1 -Share        (PowerShell)

The public link stays alive only while this window is open; Ctrl+C closes it.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # allow "python scripts/share_online.py" from anywhere
    sys.path.insert(0, str(ROOT))

from app.core.network import get_lan_ips  # noqa: E402  (stdlib-only helper)

DEFAULT_TIMEOUT = 60.0
HEALTH_PATH = "/api/health"

# Public URL shapes each provider prints (see module docstring).
URL_PATTERNS: dict[str, tuple[str, ...]] = {
    "cloudflared": (
        r"https://[a-z0-9][a-z0-9-]*\.trycloudflare\.com",
        r"https://[a-z0-9][a-z0-9-]*\.cfargotunnel\.com",
    ),
    "ngrok": (
        r"https://[a-z0-9][a-z0-9-]*\.ngrok-free\.app",
        r"https://[a-z0-9][a-z0-9-]*\.ngrok\.app",
        r"https://[a-z0-9][a-z0-9-]*\.ngrok\.io",
    ),
    "ssh": (
        r"https://[a-z0-9][a-z0-9-]*\.lhr\.life",
        r"https://[a-z0-9][a-z0-9-]*\.localhost\.run",
    ),
}

TOOL_ORDER = ("cloudflared", "ngrok", "ssh")

INSTALL_HINTS = {
    "cloudflared": "winget install --id Cloudflare.cloudflared",
    "ngrok": "winget install ngrok.ngrok && ngrok config add-authtoken <token>",
    "ssh": "enable the Windows feature 'OpenSSH Client' (Settings > Apps)",
}


def _re(pattern: str):
    """Compile one provider URL pattern (case-insensitive).

    The lookahead makes the match end at a real host boundary, so a longer
    attacker-style host (``...ngrok-free.app.evil.test``) is never truncated
    into a link that looks legitimate.
    """
    return re.compile(pattern + r"(?![A-Za-z0-9.-])", re.IGNORECASE)


COMPILED_PATTERNS = {tool: tuple(_re(p) for p in patterns)
                     for tool, patterns in URL_PATTERNS.items()}


def detect_tool(preferred: str = "auto") -> str | None:
    """Return the tunnel tool to use, or None when nothing is installed."""
    preferred = (preferred or "auto").strip().lower()
    if preferred in TOOL_ORDER:
        return preferred if shutil.which(preferred) else None
    for tool in TOOL_ORDER:
        if shutil.which(tool):
            return tool
    return None


def build_command(tool: str, port: int) -> list[str]:
    """Command line that opens a public tunnel to 127.0.0.1:<port>."""
    target = f"http://127.0.0.1:{port}"
    if tool == "cloudflared":
        return [shutil.which("cloudflared") or "cloudflared",
                "tunnel", "--url", target, "--no-autoupdate"]
    if tool == "ngrok":
        return [shutil.which("ngrok") or "ngrok", "http", str(port),
                "--log=stdout", "--log-format=logfmt"]
    if tool == "ssh":
        return [shutil.which("ssh") or "ssh",
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", "ServerAliveInterval=30",
                "-o", "ExitOnForwardFailure=yes",
                "-R", f"80:127.0.0.1:{port}",
                "nokey@localhost.run"]
    raise ValueError(f"unknown tunnel tool: {tool}")


def extract_public_url(tool: str, line: str) -> str | None:
    """Pull the public https URL out of one line of tunnel output."""
    for pattern in COMPILED_PATTERNS.get(tool, ()):
        match = pattern.search(line)
        if match:
            return match.group(0)
    return None


def ngrok_api_url(timeout: float = 1.0) -> str | None:
    """Ask ngrok's local API for the public URL (fallback for log parsing)."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels",
                                    timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError):
        return None
    for tunnel in payload.get("tunnels", []):
        candidate = str(tunnel.get("public_url", ""))
        if candidate.startswith("https://"):
            return candidate
    return None


# ---------------------------------------------------------------------------
# Process helpers
# ---------------------------------------------------------------------------
def _pump(process: subprocess.Popen, sink: "queue.Queue[str]") -> None:
    """Stream a child's stdout+stderr into a queue (one reader thread)."""
    assert process.stdout is not None
    for line in process.stdout:
        sink.put(line.rstrip("\r\n"))


def _start(command: list[str], env: dict[str, str] | None = None) -> subprocess.Popen:
    return subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
        cwd=str(ROOT),
    )


def _stop(process: subprocess.Popen | None, name: str) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
    print(f" [ok] {name} stopped")


def wait_for_health(port: int, timeout: float = 30.0, server: subprocess.Popen | None = None) -> bool:
    """Poll the server's /api/health until it answers (or the child dies)."""
    url = f"http://127.0.0.1:{port}{HEALTH_PATH}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server is not None and server.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    return False


def wait_for_public_url(tool: str, process: subprocess.Popen,
                        timeout: float) -> tuple[str | None, list[str]]:
    """Watch the tunnel output until it prints the public URL."""
    sink: "queue.Queue[str]" = queue.Queue()
    threading.Thread(target=_pump, args=(process, sink), daemon=True).start()
    log: list[str] = []
    deadline = time.monotonic() + timeout
    url: str | None = None
    while time.monotonic() < deadline:
        try:
            line = sink.get(timeout=0.5)
        except queue.Empty:
            line = ""
        if line:
            log.append(line)
            print(f"   [{tool}] {line}")
            url = extract_public_url(tool, line)
            if url:
                return url, log
        if process.poll() is not None:
            # Drain whatever is left, then give up immediately.
            while not sink.empty():
                trailing = sink.get_nowait()
                log.append(trailing)
                print(f"   [{tool}] {trailing}")
            return None, log
        if tool == "ngrok" and not line:
            url = ngrok_api_url()
            if url:
                return url, log
    return None, log


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------
def enable_windows_ansi() -> bool:
    """Turn on VT escape processing so coloured QR blocks render on cmd.exe."""
    if os.name != "nt":
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except (AttributeError, OSError):
        return False


def print_qr(url: str) -> None:
    """Render the share link as a scannable QR; never let this break sharing."""
    try:
        from app.core.qr import render_ascii

        print(render_ascii(url, error="M"))
    except Exception as exc:  # pragma: no cover - cosmetic only
        print(f" (QR unavailable: {exc}; use the link above)")


def print_banner(public_url: str | None, port: int, host: str, tool: str,
                 show_qr: bool) -> None:
    line = "=" * 78
    print()
    print(line)
    if public_url:
        print(" LearnCraft is ONLINE - open this link on any phone, anywhere:")
        print(f"   {public_url}")
    else:
        print(" LearnCraft is running (no public link was created):")
    print(line)
    if host == "0.0.0.0":
        lan = get_lan_ips()
        if lan:
            print(f" Same Wi-Fi (fastest, no internet): http://{lan[0]}:{port}")
            for extra in lan[1:]:
                print(f"                                     http://{extra}:{port}")
        else:
            print(f" Same Wi-Fi: http://<this-PC-IP>:{port} "
                  "(no private IPv4 detected - check Wi-Fi/hotspot)")
    else:
        print(f" Bound to {host} only - LAN devices cannot connect (use --host 0.0.0.0).")
    print(f" This PC    : http://localhost:{port}")
    print(f" Tunnel     : {tool} (public link changes every run on free tiers)")
    print(line)
    if show_qr and public_url:
        print(" Scan to open on a phone:")
        print()
        print_qr(public_url)
        print()
    print(" Keep this window open while students use the link.")
    print(" Press Ctrl+C to close the public link and stop the server.")
    print(line)


def access_lines_for(host: str, port: int) -> list[str]:
    """LAN URLs, for the pre-tunnel status block."""
    if host != "0.0.0.0":
        return []
    return [f"http://{ip}:{port}" for ip in get_lan_ips()]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="share_online.py",
        description="Start LearnCraft and expose it through a public HTTPS tunnel.",
    )
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("APP_PORT", "0") or 0),
                        help="local port to serve (default: APP_PORT or 5000)")
    parser.add_argument("--host", default=os.environ.get("LEARNCRAFT_SHARE_HOST", "0.0.0.0"),
                        help="bind address for the server (default 0.0.0.0 = LAN + tunnel)")
    parser.add_argument("--tool", default=os.environ.get("LEARNCRAFT_SHARE_TOOL", "auto"),
                        choices=("auto",) + TOOL_ORDER,
                        help="tunnel provider (default: auto-detect)")
    parser.add_argument("--timeout", type=float,
                        default=float(os.environ.get("LEARNCRAFT_SHARE_TIMEOUT", DEFAULT_TIMEOUT)),
                        help="seconds to wait for the public URL")
    parser.add_argument("--no-qr", action="store_true", help="do not print the QR code")
    parser.add_argument("--no-server", action="store_true",
                        help="tunnel an already-running server instead of starting one")
    return parser.parse_args(argv)


def start_server(host: str, port: int) -> subprocess.Popen:
    """Start `python server.py` with an explicit bind, echoing its output."""
    env = os.environ.copy()
    env["APP_HOST"] = host
    env["APP_PORT"] = str(port)
    env["PYTHONUNBUFFERED"] = "1"
    process = _start([sys.executable, str(ROOT / "server.py")], env=env)
    sink: "queue.Queue[str]" = queue.Queue()
    threading.Thread(target=_pump, args=(process, sink), daemon=True).start()

    def echo() -> None:
        while True:
            try:
                line = sink.get(timeout=0.5)
            except queue.Empty:
                if process.poll() is not None:
                    return
                continue
            print(f" [server] {line}")

    threading.Thread(target=echo, daemon=True).start()
    return process


def tunnel_hint(tool: str) -> str:
    """Why a tunnel may have started but never printed a public URL."""
    if tool == "ngrok":
        return ("     Check ngrok is authenticated: "
                "ngrok config add-authtoken <token>, then retry.")
    if tool == "ssh":
        return ("     localhost.run may be busy or blocked by the school network - "
                "try --tool cloudflared.")
    return ("     Check the outbound HTTPS/QUIC access on this network "
            "(some school firewalls block tunnels).")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    port = args.port or 5000
    show_qr = not args.no_qr and os.environ.get("LEARNCRAFT_SHARE_QR", "1") not in {"0", "false", "no"}
    if show_qr:
        enable_windows_ansi()

    tool = detect_tool(args.tool)
    if tool is None:
        if args.tool in TOOL_ORDER:
            print(f" [!] Requested tunnel tool '{args.tool}' is not installed "
                  "(or not on PATH).")
            print(f"     Install with: {INSTALL_HINTS[args.tool]}")
            return 2
        print(f" [!] No tunnel tool found on PATH (tried: {', '.join(TOOL_ORDER)}).")
        for hint in TOOL_ORDER:
            print(f"   - {hint}: {INSTALL_HINTS[hint]}")
        print("   cloudflared needs no account and is the quickest option;")
        print("   ssh is already present on most Windows 10+/macOS/Linux PCs.")
        return 2

    print()
    print("=" * 78)
    print(" LearnCraft - share online (public HTTPS link for phones / tablets)")
    print("=" * 78)
    print(f" Tunnel tool : {tool}")
    print(f" Bind        : {args.host}:{port}")
    for url in access_lines_for(args.host, port):
        print(f" LAN URL     : {url}")

    server: subprocess.Popen | None = None
    tunnel: subprocess.Popen | None = None
    try:
        if args.no_server:
            print(" Using the already-running server (--no-server).")
        else:
            print(" Starting server ...")
            server = start_server(args.host, port)
        if not wait_for_health(port, timeout=30.0 if not args.no_server else 5.0, server=server):
            print(f" [!] Server did not answer on http://127.0.0.1:{port}{HEALTH_PATH}")
            print("     Check the [server] lines above for the real error "
                  "(missing LEARNCRAFT_SECRET_KEY?).")
            return 3

        print(f" Opening the public tunnel via {tool} ...")
        tunnel = _start(build_command(tool, port))
        public_url, log = wait_for_public_url(tool, tunnel, args.timeout)
        if not public_url:
            print(f" [!] {tool} did not report a public URL within {args.timeout:.0f}s.")
            for line in log[-8:]:
                print(f"     {line}")
            print(tunnel_hint(tool))
            return 3

        print_banner(public_url, port, args.host, tool, show_qr)
        while tunnel.poll() is None and (server is None or server.poll() is None):
            time.sleep(0.5)
        print(" [!] Tunnel or server exited; shutting the other one down.")
        return 0
    except KeyboardInterrupt:
        print("\n Closing the public link ...")
        return 0
    finally:
        _stop(tunnel, "tunnel")
        _stop(server, "server")
        print(" Public link closed.")


if __name__ == "__main__":
    raise SystemExit(main())


