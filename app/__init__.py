"""Application package entry-point.

This keeps the project organized while preserving the existing top-level Flask app
and compatibility with the current server.py entry structure.
"""

from __future__ import annotations

from .main import app, create_app

__all__ = ["app", "create_app"]
