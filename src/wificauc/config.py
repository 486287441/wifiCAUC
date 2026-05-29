from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONFIG_FILENAME = "config.local.yaml"
EXAMPLE_FILENAME = "config.example.yaml"


@dataclass(frozen=True)
class PortalSelectors:
    username: str
    password: str
    submit: str


@dataclass(frozen=True)
class AppConfig:
    wifi_ssid: str
    wifi_interface: str
    wifi_ssid_match: str
    wifi_fallback_portal_detect: bool
    portal_url: str
    selectors: PortalSelectors
    success_text: str
    username: str
    password: str
    poll_interval_seconds: int
    connectivity_urls: list[str]
    connectivity_timeout_seconds: float
    connectivity_bind_wifi: bool
    clash_compatible: bool
    headless: bool
    portal_timeout_seconds: int


def _require_mapping(data: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"缺少或格式错误：{label}（应为对象）")
    return value


def _require_str(data: dict[str, Any], key: str, label: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"缺少或为空：{label}")
    return value.strip()


def _parse_config(raw: dict[str, Any]) -> AppConfig:
    wifi = _require_mapping(raw, "wifi", "wifi")
    portal = _require_mapping(raw, "portal", "portal")
    credentials = _require_mapping(raw, "credentials", "credentials")
    runtime = raw.get("runtime")
    if runtime is not None and not isinstance(runtime, dict):
        raise ValueError("runtime 应为对象")

    selectors_raw = _require_mapping(portal, "selectors", "portal.selectors")
    selectors = PortalSelectors(
        username=_require_str(selectors_raw, "username", "portal.selectors.username"),
        password=_require_str(selectors_raw, "password", "portal.selectors.password"),
        submit=_require_str(selectors_raw, "submit", "portal.selectors.submit"),
    )

    connectivity_urls: list[str] = []
    if isinstance(runtime, dict):
        urls = runtime.get("connectivity_urls")
        if urls is not None:
            if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
                raise ValueError("runtime.connectivity_urls 应为字符串列表")
            connectivity_urls = [u.strip() for u in urls if u.strip()]

    if not connectivity_urls:
        connectivity_urls = ["http://captive.apple.com/hotspot-detect.html"]

    wifi_interface = "auto"
    if isinstance(wifi.get("interface"), str) and wifi["interface"].strip():
        wifi_interface = wifi["interface"].strip()

    wifi_ssid_match = "normalized"
    if isinstance(wifi.get("ssid_match"), str) and wifi["ssid_match"].strip():
        wifi_ssid_match = wifi["ssid_match"].strip().lower()
        if wifi_ssid_match not in {"strict", "normalized"}:
            raise ValueError("wifi.ssid_match 应为 strict 或 normalized")

    poll_interval = 20
    headless = True
    portal_timeout = 30
    connectivity_timeout = 3.0
    connectivity_bind_wifi = True
    clash_compatible = True
    wifi_fallback_portal_detect = True
    if isinstance(runtime, dict):
        if "poll_interval_seconds" in runtime:
            poll_interval = int(runtime["poll_interval_seconds"])
        if "headless" in runtime:
            headless = bool(runtime["headless"])
        if "portal_timeout_seconds" in runtime:
            portal_timeout = int(runtime["portal_timeout_seconds"])
        if "connectivity_timeout_seconds" in runtime:
            connectivity_timeout = float(runtime["connectivity_timeout_seconds"])
        if "connectivity_bind_wifi" in runtime:
            connectivity_bind_wifi = bool(runtime["connectivity_bind_wifi"])
        if "clash_compatible" in runtime:
            clash_compatible = bool(runtime["clash_compatible"])

    if isinstance(wifi.get("fallback_portal_detect"), bool):
        wifi_fallback_portal_detect = wifi["fallback_portal_detect"]

    if clash_compatible and not connectivity_bind_wifi:
        connectivity_bind_wifi = True
    if clash_compatible:
        wifi_fallback_portal_detect = True

    return AppConfig(
        wifi_ssid=_require_str(wifi, "ssid", "wifi.ssid"),
        wifi_interface=wifi_interface,
        wifi_ssid_match=wifi_ssid_match,
        wifi_fallback_portal_detect=wifi_fallback_portal_detect,
        portal_url=_require_str(portal, "url", "portal.url"),
        selectors=selectors,
        success_text=_require_str(portal, "success_text", "portal.success_text")
        if portal.get("success_text") is not None
        else "您已经成功登录",
        username=_require_str(credentials, "username", "credentials.username"),
        password=_require_str(credentials, "password", "credentials.password"),
        poll_interval_seconds=poll_interval,
        connectivity_urls=connectivity_urls,
        connectivity_timeout_seconds=connectivity_timeout,
        connectivity_bind_wifi=connectivity_bind_wifi,
        clash_compatible=clash_compatible,
        headless=headless,
        portal_timeout_seconds=portal_timeout,
    )


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or Path(CONFIG_FILENAME)
    if not config_path.is_file():
        print(
            f"找不到配置文件：{config_path}\n"
            f"请复制 {EXAMPLE_FILENAME} 为 {CONFIG_FILENAME} 并填写账号密码。",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        with config_path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        print(f"配置文件 YAML 解析失败：{exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(raw, dict):
        print("配置文件根节点应为 YAML 对象。", file=sys.stderr)
        sys.exit(1)

    try:
        return _parse_config(raw)
    except ValueError as exc:
        print(f"配置校验失败：{exc}", file=sys.stderr)
        sys.exit(1)
