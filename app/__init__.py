"""Application package entry-point.

This keeps the project organized while preserving the existing top-level Flask app
and compatibility with the current server.py entry structure.
"""

from __future__ import annotations

from typing import Any


def create_app() -> Any:
    """Return the configured Flask app instance."""
    from server import app as flask_app

    return flask_app


app = create_app()

__all__ = ["app", "create_app"]
