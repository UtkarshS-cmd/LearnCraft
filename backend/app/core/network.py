"""LAN / hotspot discovery helpers for LearnCraft.

Stdlib-only on purpose: LearnCraft must start and report its addresses with
zero Internet access and zero third-party dependencies.

Only RFC-1918 / link-local IPv4 addresses are ever reported so a public IP
is never accidentally advertised as a classroom URL.
"""

from __future__ import annotations

import ipaddress
import socket


def _is_usable_private_ipv4(address: str) -> bool:
    """Return True for LAN/hotspot addresses worth showing to a teacher."""
    try:
        ip = ipaddress.ip_address(address.strip())
    except ValueError:
        return False
    if not isinstance(ip, ipaddress.IPv4Address):
        return False
    if ip.is_loopback or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return False
    # Classroom-reachable ranges: 10/8, 172.16/12, 192.168/16 + link-local
    # 169.254/16 (Windows hotspot / ad-hoc networks often land here).
    return ip.is_private or ip.is_link_local


def get_lan_ips() -> list[str]:
    """Best-effort list of private IPv4 addresses for this machine.

    Strategy (all offline-safe, no Internet needed):
      1. Resolve the local hostname (covers most laptops with one Wi-Fi NIC).
      2. Open a UDP socket to a LAN address and read the chosen source IP.
         No packet is ever sent — connect() on UDP only selects an interface.
      3. Deduplicate, keep only usable private IPv4, sorted for stable output.
    Never raises: returns [] when nothing usable is found.
    """
    found: list[str] = []

    def _add(value: str | None) -> None:
        if value and value not in found:
            found.append(value)

    # 1. Hostname resolution.
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_DGRAM):
            _add(info[4][0])
    except OSError:
        pass

    # 2. Interface selected for LAN traffic (no packet sent).
    for target in ("192.168.1.1", "10.0.0.1"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect((target, 80))
                _add(probe.getsockname()[0])
        except OSError:
            continue

    usable = [ip for ip in found if _is_usable_private_ipv4(ip)]
    # Sort numerically for deterministic terminal output.
    try:
        usable.sort(key=lambda ip: tuple(int(part) for part in ip.split(".")))
    except ValueError:
        usable.sort()
    return usable


def format_access_lines(port: int) -> list[str]:
    """Human-friendly startup lines, e.g. for the console banner."""
    lines = [f"Local: http://localhost:{port}"]
    ips = get_lan_ips()
    if ips:
        for ip in ips:
            lines.append(f"LAN:   http://{ip}:{port}")
    else:
        lines.append("LAN:   (no private IPv4 detected — check Wi-Fi/hotspot)")
    return lines


__all__ = ["format_access_lines", "get_lan_ips"]
