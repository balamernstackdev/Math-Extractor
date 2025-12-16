"""
IP allowlist guard for the desktop EXE.

Design:
- Fetch public IP from a lightweight service.
- Compare against a configured allowlist.
- Return False (deny) on missing IP when a list is configured.
"""
from __future__ import annotations

import httpx

from core.logger import logger


DEFAULT_IP_SERVICE = "https://api.ipify.org"


def get_public_ip(timeout: float = 3.0) -> str | None:
    """Return public IP, or None on failure."""
    try:
        resp = httpx.get(DEFAULT_IP_SERVICE, params={"format": "text"}, timeout=timeout)
        resp.raise_for_status()
        ip = resp.text.strip()
        return ip or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("IP allowlist: failed to detect public IP: %s", exc)
        return None


def is_ip_allowed(allowlist: set[str], ip: str | None) -> bool:
    """Check if ip is in allowlist. Empty allowlist means allow all."""
    if not allowlist:
        return True
    if not ip:
        return False
    return ip in allowlist


def enforce_ip_allowlist(allowlist: set[str]) -> bool:
    """
    Validate current public IP against allowlist.
    Returns True if allowed, False otherwise.
    """
    ip = get_public_ip()
    allowed = is_ip_allowed(allowlist, ip)
    if not allowed:
        logger.error("IP allowlist blocked this machine (ip=%s)", ip or "unknown")
    else:
        logger.info("IP allowlist passed (ip=%s)", ip or "unknown")
    return allowed

