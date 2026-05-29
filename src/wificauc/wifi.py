from __future__ import annotations

import re
import subprocess

_AIRPORT_CLI = (
    "/System/Library/PrivateFrameworks/Apple80211.framework"
    "/Versions/Current/Resources/airport"
)


def normalize_ssid(name: str) -> str:
    """Lowercase and strip separators for flexible matching (CAUC-WIFI ≈ caucwifi)."""
    return re.sub(r"[-_\s]", "", name.strip().lower())


def find_wifi_interface() -> str | None:
    """Return the device name for the Wi-Fi hardware port, e.g. en0."""
    try:
        result = subprocess.run(
            ["networksetup", "-listallhardwareports"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    current_port: str | None = None
    for line in (result.stdout or "").splitlines():
        if line.startswith("Hardware Port:"):
            current_port = line.split(":", 1)[1].strip()
            continue
        if line.startswith("Device:") and current_port == "Wi-Fi":
            return line.split(":", 1)[1].strip()
    return None


def resolve_wifi_interface(preferred: str = "auto") -> str:
    """Resolve configured interface; `auto` picks the Wi-Fi device from networksetup."""
    preferred = preferred.strip()
    if preferred and preferred.lower() != "auto":
        return preferred
    return find_wifi_interface() or "en0"


def _is_clash_virtual_ip(ip: str) -> bool:
    """Clash TUN / fake-ip often uses 10.8.x.x or 198.18.x.x on Wi-Fi interface."""
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        a, b = int(parts[0]), int(parts[1])
    except ValueError:
        return False
    if a == 10 and b == 8:
        return True
    if a == 198 and b == 18:
        return True
    return False


def _list_interface_ipv4_addresses(interface: str) -> list[str]:
    try:
        result = subprocess.run(
            ["ifconfig", interface],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    return re.findall(r"\binet (\d+\.\d+\.\d+\.\d+)\b", result.stdout or "")


def get_interface_ipv4(interface: str) -> str | None:
    """Return IPv4 for HTTP bind; skip Clash virtual addresses on the Wi-Fi NIC."""
    for ip in _list_interface_ipv4_addresses(interface):
        if ip.startswith("192.168.") and not _is_clash_virtual_ip(ip):
            return ip
    try:
        result = subprocess.run(
            ["ipconfig", "getifaddr", interface],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    ip = (result.stdout or "").strip()
    if not ip or ip == "0.0.0.0" or _is_clash_virtual_ip(ip):
        return None
    return ip


def _parse_ssid_from_networksetup_output(text: str) -> str | None:
    text = text.strip()
    if not text:
        return None
    lowered = text.lower()
    if "not associated" in lowered or "未关联" in text or "没有关联" in text:
        return None
    match = re.search(r"[:：]\s*(.+)\s*$", text)
    if not match:
        return None
    ssid = match.group(1).strip()
    return ssid or None


def _get_ssid_via_networksetup(interface: str) -> str | None:
    try:
        result = subprocess.run(
            ["networksetup", "-getairportnetwork", interface],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return _parse_ssid_from_networksetup_output(result.stdout or "")


def _get_ssid_via_airport(interface: str) -> str | None:
    import os

    if not os.path.isfile(_AIRPORT_CLI):
        return None
    try:
        result = subprocess.run(
            [_AIRPORT_CLI, "-I", interface],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    match = re.search(r"(?:^|\n)\s*SSID:\s*(.+?)\s*$", result.stdout or "", re.MULTILINE)
    if not match:
        return None
    ssid = match.group(1).strip()
    return ssid or None


def get_current_ssid(interface: str = "en0") -> str | None:
    """Return the current Wi-Fi SSID, or None if unavailable / not connected."""
    ssid = _get_ssid_via_networksetup(interface)
    if ssid:
        return ssid
    return _get_ssid_via_airport(interface)


def is_target_wifi(
    ssid: str | None,
    target: str,
    *,
    match_mode: str = "normalized",
) -> bool:
    """Match SSID; normalized ignores case and `-` / `_` / spaces."""
    if ssid is None:
        return False
    if match_mode == "strict":
        return ssid.strip() == target.strip()
    return normalize_ssid(ssid) == normalize_ssid(target)
