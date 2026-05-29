#!/usr/bin/env bash
# M02 自动化验收：单元 + 集成 mock + 本机 once 冒烟
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

echo "== 1/3 单元测试 test_m02 =="
python -m unittest tests.test_m02 -v

echo ""
echo "== 2/3 验收测试 test_m02_acceptance =="
python -m unittest tests.test_m02_acceptance -v

echo ""
echo "== 3/3 本机 once 冒烟 =="
OUT=$(WIFICAUC_SKIP_LOGIN=1 python -m wificauc.main once 2>&1) || true
echo "$OUT"
if echo "$OUT" | grep -qE 'skipped: wrong wifi|skipped: already online|need_portal_login'; then
  echo "PASS: once 输出符合 M02 三分支之一"
else
  echo "FAIL: once 输出无法识别" >&2
  exit 1
fi

echo ""
echo "== WiFi 诊断 =="
python3 <<'PY'
from wificauc.config import load_config
from wificauc.wifi import get_current_ssid, get_interface_ipv4, resolve_wifi_interface

cfg = load_config()
iface = resolve_wifi_interface(cfg.wifi_interface)
ssid = get_current_ssid(iface)
bind = get_interface_ipv4(iface)
print(f"  interface: {iface}")
print(f"  SSID: {ssid or '(hidden / unknown)'}")
print(f"  bind_ip: {bind or '(none — use system route via Clash DIRECT)'}")
print(f"  clash_compatible: {cfg.clash_compatible}")
print(f"  portal_fallback: {cfg.wifi_fallback_portal_detect}")
PY

if echo "$OUT" | grep -q "need_portal_login"; then
  echo "NOTE: 本机当前可走门户登录分支（Clash/校园网环境正常）"
elif echo "$OUT" | grep -q "skipped: already online"; then
  echo "NOTE: 本机当前已登录校园网门户"
elif echo "$OUT" | grep -q "detect: portal"; then
  echo "NOTE: 通过门户探测识别校园网（SSID 被 Clash 隐藏）"
fi

echo ""
echo "M02 自动化验收全部通过。"
