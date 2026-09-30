"""Deployment configuration tests: host/port/env/CORS/.env/LAN discovery.

Offline-safe by design: no sockets leave the machine (LAN discovery only
reads local interface addresses), no third-party packages required.
"""

import importlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _reload_config(env):
    for key in list(os.environ):
        if key in env or key.startswith(("APP_", "CORS_", "PORT", "HOST")):
            os.environ.pop(key, None)
    os.environ.update(env)
    import app.core.config as config_module

    return importlib.reload(config_module)


class DeploymentConfigTests(unittest.TestCase):
    def setUp(self):
        self._saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved)
        import app.core.config as config_module

        importlib.reload(config_module)

    def test_host_port_defaults_local_only(self):
        config = _reload_config({"LEARNCRAFT_SECRET_KEY": "x"})
        self.assertEqual(config.get_host(), "127.0.0.1")
        self.assertEqual(config.get_port(), 5000)

    def test_host_port_env_override(self):
        config = _reload_config({
            "LEARNCRAFT_SECRET_KEY": "x",
            "APP_HOST": "0.0.0.0",
            "APP_PORT": "8080",
        })
        self.assertEqual(config.get_host(), "0.0.0.0")
        self.assertEqual(config.get_port(), 8080)

    def test_bad_port_falls_back(self):
        config = _reload_config({"LEARNCRAFT_SECRET_KEY": "x", "APP_PORT": "abc"})
        self.assertEqual(config.get_port(), 5000)
        config = _reload_config({"LEARNCRAFT_SECRET_KEY": "x", "APP_PORT": "99999"})
        self.assertEqual(config.get_port(), 5000)

    def test_cors_defaults_empty_dev_allows_star(self):
        config = _reload_config({"LEARNCRAFT_SECRET_KEY": "x"})
        self.assertEqual(config.get_cors_origins(), [])
        config = _reload_config({
            "LEARNCRAFT_SECRET_KEY": "x",
            "CORS_ORIGINS": "https://a.example, https://b.example/",
            "APP_ENV": "development",
        })
        self.assertEqual(
            config.get_cors_origins(), ["https://a.example", "https://b.example"]
        )

    def test_cors_wildcard_ignored_in_production(self):
        config = _reload_config({
            "LEARNCRAFT_SECRET_KEY": "x",
            "CORS_ORIGINS": "*",
            "APP_ENV": "production",
        })
        self.assertEqual(config.get_cors_origins(), [])

    def test_debug_never_on_in_production(self):
        config = _reload_config({
            "LEARNCRAFT_SECRET_KEY": "x",
            "APP_ENV": "production",
            "FLASK_DEBUG": "1",
            "APP_DEBUG": "1",
        })
        self.assertFalse(config.is_debug_enabled())
        self.assertTrue(config.is_production())
        self.assertTrue(config.should_trust_proxy())

    def test_dotenv_loader_does_not_override_env(self):
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as handle:
            handle.write("APP_PORT=7777\nAPP_HOST=0.0.0.0\n")
            path = handle.name
        try:
            config = _reload_config({"LEARNCRAFT_SECRET_KEY": "x", "APP_PORT": "5000"})
            self.assertEqual(config.load_dotenv(path), path)
            # Real env wins over the file.
            self.assertEqual(os.environ["APP_PORT"], "5000")
            self.assertEqual(os.environ["APP_HOST"], "0.0.0.0")
        finally:
            os.unlink(path)

    def test_lan_discovery_never_raises_and_filters(self):
        from app.core.network import _is_usable_private_ipv4, get_lan_ips

        self.assertTrue(_is_usable_private_ipv4("192.168.1.10"))
        self.assertTrue(_is_usable_private_ipv4("10.0.0.5"))
        self.assertFalse(_is_usable_private_ipv4("127.0.0.1"))
        self.assertFalse(_is_usable_private_ipv4("8.8.8.8"))
        self.assertFalse(_is_usable_private_ipv4("not-an-ip"))
        ips = get_lan_ips()
        self.assertIsInstance(ips, list)
        for ip in ips:
            self.assertTrue(_is_usable_private_ipv4(ip))


class DatabasePathResolutionTests(unittest.TestCase):
    """SQLite location resolves from LEARNCRAFT_DB_PATH or DATABASE_URL.

    Container/PaaS hosts often inject DATABASE_URL instead of the LearnCraft
    specific name, so both spellings must land on the same file.
    """

    def setUp(self):
        self._saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved)

    @staticmethod
    def _connection():
        from app.database import connection

        return connection

    def test_default_is_backend_data_dir(self):
        os.environ.pop("LEARNCRAFT_DB_PATH", None)
        os.environ.pop("DATABASE_URL", None)
        connection = self._connection()
        self.assertEqual(
            connection.resolve_db_path(), (connection.DATA_DIR / "learncraft.db").resolve()
        )

    def test_relative_path_resolves_against_project_root(self):
        os.environ.pop("DATABASE_URL", None)
        os.environ["LEARNCRAFT_DB_PATH"] = "data/custom.db"
        connection = self._connection()
        self.assertEqual(
            connection.resolve_db_path(),
            (connection.BASE_DIR / "data" / "custom.db").resolve(),
        )

    def test_absolute_path_is_kept(self):
        os.environ.pop("DATABASE_URL", None)
        target = Path(tempfile.gettempdir()) / "learncraft_abs_path.db"
        os.environ["LEARNCRAFT_DB_PATH"] = str(target)
        connection = self._connection()
        self.assertEqual(connection.resolve_db_path(), target)

    def test_database_url_sqlite_forms_are_normalised(self):
        os.environ.pop("LEARNCRAFT_DB_PATH", None)
        connection = self._connection()
        for url, expected in (
            ("sqlite:///relative.sqlite", "relative.sqlite"),
            ("sqlite:////srv/learncraft.db", "/srv/learncraft.db"),
            ("sqlite:///:memory:", ":memory:"),
            ("sqlite:///C:/data/learncraft.db", "C:/data/learncraft.db"),
            ("sqlite://", ""),
        ):
            os.environ["DATABASE_URL"] = url
            self.assertEqual(connection._configured_db_value(), expected, url)

    def test_database_url_relative_resolves_against_project_root(self):
        os.environ.pop("LEARNCRAFT_DB_PATH", None)
        os.environ["DATABASE_URL"] = "sqlite:///data/url.db"
        connection = self._connection()
        self.assertEqual(
            connection.resolve_db_path(), (connection.BASE_DIR / "data" / "url.db").resolve()
        )

    def test_learncraft_db_path_wins_over_database_url(self):
        os.environ["LEARNCRAFT_DB_PATH"] = "data/winner.db"
        os.environ["DATABASE_URL"] = "sqlite:///data/loser.db"
        connection = self._connection()
        self.assertEqual(connection._configured_db_value(), "data/winner.db")

    def test_bare_sqlite_url_falls_back_to_default(self):
        os.environ.pop("LEARNCRAFT_DB_PATH", None)
        os.environ["DATABASE_URL"] = "sqlite://"
        connection = self._connection()
        self.assertEqual(
            connection.resolve_db_path(), (connection.DATA_DIR / "learncraft.db").resolve()
        )


class ComposeEmptyEnvBootTests(unittest.TestCase):
    """docker-compose passes optional vars as EMPTY strings when docker/.env
    leaves them unset (VAR=${VAR:-}). Boot must treat "" like "unset": the old
    int(os.environ.get(..., "587")) crashed every gunicorn worker with
    ValueError: int("") on `docker compose up` (offline-safe: subprocess only
    imports the app locally, no sockets)."""

    def test_app_boots_and_defaults_mail_when_env_vars_are_empty(self):
        backend_dir = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env.update(
                {
                    "LEARNCRAFT_SECRET_KEY": "compose-empty-env-test",
                    "LEARNCRAFT_DB_PATH": os.path.join(tmp, "boot.db"),
                    "LEARNCRAFT_MAIL_HOST": "",
                    "LEARNCRAFT_MAIL_PORT": "",
                    "LEARNCRAFT_MAIL_USERNAME": "",
                    "LEARNCRAFT_MAIL_PASSWORD": "",
                    "LEARNCRAFT_MAIL_FROM": "",
                }
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from app.main import app; "
                    "print('MAIL_PORT', app.config['MAIL_PORT']); "
                    "print('MAIL_FROM', app.config['MAIL_FROM']); "
                    "print('MAIL_HOST', app.config['MAIL_HOST'])",
                ],
                cwd=str(backend_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
            self.assertIn("MAIL_PORT 587", proc.stdout)
            self.assertIn("MAIL_FROM no-reply@learncraft.local", proc.stdout)
            self.assertIn("MAIL_HOST None", proc.stdout)


if __name__ == "__main__":
    unittest.main()
