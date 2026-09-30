"""Compatibility entry point for running LearnCraft from the repository root."""
from app.core.config import get_host, get_port, is_debug_enabled
from app.core.network import format_access_lines
from app.main import app, create_app

__all__ = ["app", "create_app"]


if __name__ == "__main__":
    host = get_host("127.0.0.1")
    port = get_port(5000)
    print(" LearnCraft Local Server")
    for line in format_access_lines(port):
        print(f" {line}")
    print(f" Listening on {host}:{port} "
          f"({'all interfaces' if host == '0.0.0.0' else 'local-only'}).")
    # Never enable the Werkzeug debugger by default: when bound to 0.0.0.0
    # any LAN neighbour could otherwise execute code via the debug console.
    app.run(host=host, port=port, debug=is_debug_enabled())
