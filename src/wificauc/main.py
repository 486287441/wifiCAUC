from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

from wificauc.clash import is_clash_running
from wificauc.config import AppConfig, load_config
from wificauc.connectivity import (
    is_internet_available,
    portal_host_from_url,
    probe_portal_reachable,
)
from wificauc.notify import notify_failure, notify_success
from wificauc.portal import login as portal_login
from wificauc.state import (
    clear_paused,
    is_paused,
    read_last_run,
    read_paused,
    set_paused,
    write_last_run,
)
from wificauc.wifi import (
    get_current_ssid,
    get_interface_ipv4,
    is_target_wifi,
    resolve_wifi_interface,
)


def ssid_just_joined_target(
    last_ssid: str | None,
    current_ssid: str | None,
    target_ssid: str,
    *,
    match_mode: str,
) -> bool:
    """True when SSID transitions from non-target to target (incl. first poll)."""
    on_target = is_target_wifi(current_ssid, target_ssid, match_mode=match_mode)
    was_on_target = is_target_wifi(last_ssid, target_ssid, match_mode=match_mode)
    return on_target and not was_on_target


def _on_target_network(
    cfg: AppConfig,
    current_ssid: str | None,
    *,
    bind_ip: str | None,
) -> tuple[bool, str]:
    if is_target_wifi(
        current_ssid,
        cfg.wifi_ssid,
        match_mode=cfg.wifi_ssid_match,
    ):
        return True, "ssid"

    if current_ssid is not None:
        return False, "ssid_mismatch"

    if cfg.wifi_fallback_portal_detect:
        portal_host = portal_host_from_url(cfg.portal_url)
        portal_probe = probe_portal_reachable(
            cfg.portal_url,
            portal_host,
            success_text=cfg.success_text,
            bind_ip=bind_ip,
            timeout=cfg.connectivity_timeout_seconds,
        )
        if portal_probe is not None:
            return True, "portal"

    return False, "unknown"


def decide_once_outcome(
    cfg: AppConfig,
    current_ssid: str | None,
    *,
    bind_ip: str | None = None,
    force_login: bool = False,
) -> str:
    """
    Return one of: wrong_wifi | already_online | need_portal_login
    """
    on_target, _reason = _on_target_network(cfg, current_ssid, bind_ip=bind_ip)
    if not on_target:
        return "wrong_wifi"

    if not force_login:
        portal_host = portal_host_from_url(cfg.portal_url)
        if is_internet_available(
            cfg.connectivity_urls,
            portal_host,
            portal_url=cfg.portal_url,
            success_text=cfg.success_text,
            bind_ip=bind_ip,
            timeout=cfg.connectivity_timeout_seconds,
            clash_compatible=cfg.clash_compatible,
        ):
            return "already_online"

    return "need_portal_login"


def run_once(cfg: AppConfig, *, force_login: bool = False) -> int:
    wifi_interface = resolve_wifi_interface(cfg.wifi_interface)
    current_ssid = get_current_ssid(wifi_interface)
    bind_ip = (
        get_interface_ipv4(wifi_interface)
        if cfg.connectivity_bind_wifi
        else None
    )
    on_target, detect_reason = _on_target_network(cfg, current_ssid, bind_ip=bind_ip)
    outcome = decide_once_outcome(
        cfg, current_ssid, bind_ip=bind_ip, force_login=force_login
    )
    clash_note = "on" if cfg.clash_compatible else "off"
    if cfg.clash_compatible and is_clash_running():
        clash_note = "on (clash detected)"

    if outcome == "wrong_wifi":
        print("skipped: wrong wifi")
        if current_ssid:
            print(f"  current: {current_ssid}")
        else:
            print("  current: (not connected or unknown)")
        print(f"  expected: {cfg.wifi_ssid}")
        print(f"  interface: {wifi_interface}")
        return 0

    if outcome == "already_online":
        print("skipped: already online")
        if current_ssid:
            print(f"  SSID: {current_ssid}")
        else:
            print(f"  detect: {detect_reason} (SSID hidden by Clash)")
        print(f"  clash_compatible: {clash_note}")
        print("  hint: 若实际未登录，请用 ./start.sh force 强制尝试门户登录")
        if bind_ip:
            print(f"  bind_ip: {bind_ip}")
        write_last_run("skipped")
        return 0

    print("need_portal_login")
    if current_ssid:
        print(f"  SSID: {current_ssid}")
    else:
        print(f"  detect: {detect_reason} (SSID hidden by Clash)")
    print(f"  portal: {cfg.portal_url}")
    print(f"  clash_compatible: {clash_note}")
    if bind_ip:
        print(f"  bind_ip: {bind_ip}")

    if is_paused():
        paused = read_paused()
        print("login: skipped (paused)")
        if paused:
            reason, timestamp = paused
            if reason:
                print(f"  reason: {reason}")
            if timestamp:
                print(f"  since: {timestamp}")
        print("  hint: 修复账号密码后执行 python -m wificauc.main resume")
        return 0

    if os.environ.get("WIFICAUC_SKIP_LOGIN") == "1":
        print("login: skipped (WIFICAUC_SKIP_LOGIN=1)")
        return 0

    print("login: starting (headless browser)...")
    result = asyncio.run(portal_login(cfg))
    if result.ok and result.already_logged_in:
        print("login: already_logged_in")
        print("  note: 门户已是登录态，未填写账号或点击登录（不会点注销）")
        write_last_run("skipped")
        return 0
    if result.ok:
        print("login: success")
        print("  note: 已提交账号密码并完成门户登录")
        notify_success()
        write_last_run("success")
        return 0

    print(f"login: failed ({result.reason})")
    notify_failure(result.reason)
    write_last_run("fail")
    set_paused(result.reason)
    return 1


def cmd_once(args: argparse.Namespace) -> int:
    cfg = load_config()
    force_login = getattr(args, "force", False) is True
    return run_once(cfg, force_login=force_login)


def cmd_run(_args: argparse.Namespace) -> int:
    cfg = load_config()
    wifi_interface = resolve_wifi_interface(cfg.wifi_interface)
    print(f"run: polling every {cfg.poll_interval_seconds}s (Ctrl+C to stop)")
    last_ssid: str | None = None
    try:
        while True:
            if is_paused():
                print(f"run: paused, sleeping {cfg.poll_interval_seconds}s")
                time.sleep(cfg.poll_interval_seconds)
                continue

            current_ssid = get_current_ssid(wifi_interface)
            just_joined = ssid_just_joined_target(
                last_ssid,
                current_ssid,
                cfg.wifi_ssid,
                match_mode=cfg.wifi_ssid_match,
            )

            run_once(cfg)
            last_ssid = current_ssid

            if just_joined:
                print("run: joined target WiFi, running extra round immediately")
                run_once(cfg)
                last_ssid = get_current_ssid(wifi_interface)

            time.sleep(cfg.poll_interval_seconds)
    except KeyboardInterrupt:
        print("\nrun: stopped")
        return 0


def cmd_resume(_args: argparse.Namespace) -> int:
    cfg = load_config()
    if clear_paused():
        print("resume: paused cleared")
    else:
        print("resume: not paused")
    print("resume: running one round...")
    return run_once(cfg)


def cmd_status(_args: argparse.Namespace) -> int:
    cfg = load_config()
    wifi_interface = resolve_wifi_interface(cfg.wifi_interface)
    current_ssid = get_current_ssid(wifi_interface)

    if is_paused():
        paused = read_paused()
        print("paused: yes")
        if paused:
            reason, timestamp = paused
            if reason:
                print(f"  reason: {reason}")
            if timestamp:
                print(f"  since: {timestamp}")
    else:
        print("paused: no")

    last_run = read_last_run()
    if last_run:
        print(f"last_run: {last_run['result']} @ {last_run['timestamp']}")
    else:
        print("last_run: (none)")

    if current_ssid:
        print(f"SSID: {current_ssid}")
    else:
        print("SSID: (not connected or unknown)")
    print(f"expected: {cfg.wifi_ssid}")
    print(f"interface: {wifi_interface}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wificauc",
        description="CAUC 校园网门户自动登录",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    once_parser = sub.add_parser("once", help="检测 WiFi / 外网，判断是否需要门户登录")
    once_parser.add_argument(
        "--force",
        action="store_true",
        help="跳过「已上网」检测，强制打开门户尝试登录",
    )
    sub.add_parser("run", help="常驻轮询模式")
    sub.add_parser("resume", help="清除暂停状态后继续")
    sub.add_parser("status", help="查看运行状态")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "once": cmd_once,
        "run": cmd_run,
        "resume": cmd_resume,
        "status": cmd_status,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
