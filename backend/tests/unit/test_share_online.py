"""Tests for scripts/share_online.py (public-tunnel sharing).

Offline by design: tunnel providers are never launched. Detection is exercised
by patching ``shutil.which``, URL parsing against real provider output samples,
and the log-streaming path against a plain Python child process.
"""

import contextlib
import importlib.util
import io
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

BACKEND = Path(__file__).resolve().parents[2]
SCRIPT = BACKEND / "scripts" / "share_online.py"

spec = importlib.util.spec_from_file_location("learncraft_share_online", SCRIPT)
share = importlib.util.module_from_spec(spec)
spec.loader.exec_module(share)


CLOUDFLARED_OUTPUT = [
    "2026-09-30T10:00:00Z INF Thank you for trying Cloudflare Tunnel.",
    "2026-09-30T10:00:01Z INF Requesting new quick Tunnel on trycloudflare.com...",
    "2026-09-30T10:00:03Z INF |  Your quick Tunnel has been created! Visit it at "
    "(it may take some time to be reachable):  |",
    "2026-09-30T10:00:03Z INF |  https://random-fox-jumps-42.trycloudflare.com  |",
]

NGROK_OUTPUT = [
    "t=2026-09-30T10:00:00+0000 lvl=info msg=\"started tunnel\" "
    "name=command_line addr=http://localhost:5000 "
    "url=https://plain-grown-lines.ngrok-free.app",
]

SSH_OUTPUT = [
    "Warning: Permanently added the ED25519 host key for IP address "
    "'35.171.254.69' to the list of known hosts.",
    "2ddff6f52fa1e3.lhr.life tunneled with tls termination, "
    "https://2ddff6f52fa1e3.lhr.life",
]


class DetectToolTests(unittest.TestCase):
    def _which(self, available):
        return lambda name: f"/usr/bin/{name}" if name in available else None

    def test_auto_prefers_cloudflared_then_ngrok_then_ssh(self):
        with mock.patch("shutil.which", self._which({"cloudflared", "ngrok", "ssh"})):
            self.assertEqual(share.detect_tool("auto"), "cloudflared")
        with mock.patch("shutil.which", self._which({"ngrok", "ssh"})):
            self.assertEqual(share.detect_tool("auto"), "ngrok")
        with mock.patch("shutil.which", self._which({"ssh"})):
            self.assertEqual(share.detect_tool("auto"), "ssh")

    def test_no_tunnel_tool_installed(self):
        with mock.patch("shutil.which", self._which(set())):
            self.assertIsNone(share.detect_tool("auto"))

    def test_explicit_tool_respected_and_must_exist(self):
        with mock.patch("shutil.which", self._which({"ssh"})):
            self.assertEqual(share.detect_tool("ssh"), "ssh")
            self.assertIsNone(share.detect_tool("cloudflared"))


class CommandTests(unittest.TestCase):
    def test_cloudflared_needs_no_account(self):
        with mock.patch("shutil.which", lambda name: name):
            command = share.build_command("cloudflared", 5055)
        self.assertEqual(command[1:3], ["tunnel", "--url"])
        self.assertIn("http://127.0.0.1:5055", command)
        self.assertIn("--no-autoupdate", command)

    def test_ngrok_forwards_the_local_port(self):
        with mock.patch("shutil.which", lambda name: name):
            command = share.build_command("ngrok", 5055)
        self.assertIn("5055", command)
        self.assertIn("--log=stdout", command)

    def test_ssh_forwarding_is_safe_and_non_interactive(self):
        with mock.patch("shutil.which", lambda name: name):
            command = share.build_command("ssh", 5055)
        self.assertIn("80:127.0.0.1:5055", command)
        self.assertIn("StrictHostKeyChecking=accept-new", command)
        self.assertIn("ExitOnForwardFailure=yes", command)
        self.assertEqual(command[-1], "nokey@localhost.run")

    def test_unknown_tool_rejected(self):
        with self.assertRaises(ValueError):
            share.build_command("teamviewer", 5000)


class UrlParsingTests(unittest.TestCase):
    def test_cloudflared_quick_tunnel(self):
        urls = [share.extract_public_url("cloudflared", line)
                for line in CLOUDFLARED_OUTPUT]
        self.assertIn("https://random-fox-jumps-42.trycloudflare.com", urls)

    def test_ngrok_log_line(self):
        self.assertEqual(share.extract_public_url("ngrok", NGROK_OUTPUT[0]),
                         "https://plain-grown-lines.ngrok-free.app")

    def test_localhost_run_line(self):
        self.assertEqual(share.extract_public_url("ssh", SSH_OUTPUT[1]),
                         "https://2ddff6f52fa1e3.lhr.life")

    def test_ignores_local_and_unrelated_urls(self):
        noise = [
            "INF Requesting new quick Tunnel on trycloudflare.com...",
            "Listening on http://127.0.0.1:5000",
            "LAN: http://192.168.1.10:5000",
            "https://not-a-tunnel.example.com",
            "https://plain-grown-lines.ngrok-free.app.evil.test",
        ]
        for tool in share.TOOL_ORDER:
            for line in noise:
                self.assertIsNone(share.extract_public_url(tool, line), line)

    def test_patterns_require_https(self):
        self.assertIsNone(share.extract_public_url(
            "cloudflared", "http://random-fox-jumps-42.trycloudflare.com"))


class StreamingTests(unittest.TestCase):
    """Exercise the child-process log reader with a plain Python child."""

    def _child(self, lines):
        code = "; ".join(f"print({line!r})" for line in lines) or "pass"
        return share._start([sys.executable, "-u", "-c", code])

    def test_reports_url_from_child_output(self):
        child = self._child(CLOUDFLARED_OUTPUT)
        try:
            with contextlib.redirect_stdout(io.StringIO()) as captured:
                url, log = share.wait_for_public_url("cloudflared", child, timeout=20)
        finally:
            child.wait(timeout=10)
        self.assertEqual(url, "https://random-fox-jumps-42.trycloudflare.com")
        self.assertEqual(len(log), len(CLOUDFLARED_OUTPUT))
        self.assertIn("trycloudflare.com", captured.getvalue())

    def test_reports_failure_when_child_exits_without_url(self):
        child = self._child(["starting up", "no url here"])
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                url, log = share.wait_for_public_url("ssh", child, timeout=20)
        finally:
            child.wait(timeout=10)
        self.assertIsNone(url)
        self.assertEqual(log, ["starting up", "no url here"])

    def test_timeout_when_child_stays_silent(self):
        child = share._start([sys.executable, "-u", "-c", "import time; time.sleep(30)"])
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                url, log = share.wait_for_public_url("ngrok", child, timeout=2)
        finally:
            share._stop(child, "child")
        self.assertIsNone(url)
        self.assertEqual(log, [])


class ArgumentTests(unittest.TestCase):
    def test_defaults_come_from_the_environment(self):
        env = {"APP_PORT": "8123", "LEARNCRAFT_SHARE_TOOL": "ssh"}
        with mock.patch.dict(os.environ, env, clear=False):
            args = share.parse_args([])
        self.assertEqual(args.port, 8123)
        self.assertEqual(args.tool, "ssh")
        self.assertEqual(args.host, "0.0.0.0")
        self.assertFalse(args.no_qr)

    def test_flags(self):
        args = share.parse_args(["--port", "6000", "--tool", "ngrok",
                                 "--no-qr", "--no-server", "--timeout", "5"])
        self.assertEqual(args.port, 6000)
        self.assertTrue(args.no_qr)
        self.assertTrue(args.no_server)
        self.assertEqual(args.timeout, 5.0)

    def test_unknown_tool_is_rejected_by_argparse(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                share.parse_args(["--tool", "teamviewer"])


class MainExitCodeTests(unittest.TestCase):
    """No tunnel provider, no server, no network: just the guard rails."""

    def test_explicit_missing_tool_exits_two(self):
        with mock.patch.object(share, "detect_tool", return_value=None):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = share.main(["--tool", "cloudflared"])
        self.assertEqual(code, 2)
        self.assertIn("cloudflared", output.getvalue())

    def test_no_tool_at_all_lists_the_options(self):
        with mock.patch.object(share, "detect_tool", return_value=None):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = share.main([])
        self.assertEqual(code, 2)
        text = output.getvalue()
        for tool in share.TOOL_ORDER:
            self.assertIn(tool, text)


if __name__ == "__main__":
    unittest.main()

