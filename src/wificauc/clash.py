from __future__ import annotations

import subprocess
from urllib.parse import urlparse


def is_clash_running() -> bool:
    """Best-effort detect Clash / ClashX / Clash Verge etc."""
    try:
        result = subprocess.run(
            ["pgrep", "-if", "clash"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def portal_no_proxy_bypass(portal_url: str) -> list[str]:
    """Hosts that Playwright should reach directly (not via Clash)."""
    host = urlparse(portal_url).hostname
    if not host:
        return ["<local>", "127.0.0.1", "localhost"]
    return ["<local>", "127.0.0.1", "localhost", host, f"{host}:*"]
