#!/usr/bin/env bash
# wifiCAUC 一键启动：准备环境并执行一轮检测/自动登录（注销后无外网也可跑）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:}"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { printf "${CYAN}==>${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}!!>${NC} %s\n" "$*"; }

PYTHON="${ROOT}/.venv/bin/python"
PIP="${ROOT}/.venv/bin/pip"

has_internet() {
  ping -c 1 -W 2 1.1.1.1 &>/dev/null || ping -c 1 -W 2 192.168.4.252 &>/dev/null
}

# ---------- 虚拟环境 ----------
if [[ ! -d .venv ]]; then
  if ! has_internet; then
    warn "无 .venv 且无外网。请先连网执行: ./setup.sh"
    exit 1
  fi
  log "创建 Python 虚拟环境 .venv"
  python3 -m venv .venv
fi

if [[ ! -x "$PYTHON" ]]; then
  warn "虚拟环境损坏，请连网后执行: rm -rf .venv && ./setup.sh"
  exit 1
fi

# ---------- 第三方依赖（playwright / pyyaml）----------
need_pip_install=false
if ! "$PYTHON" -c "import playwright, yaml" 2>/dev/null; then
  need_pip_install=true
fi

if $need_pip_install; then
  if has_internet; then
    log "安装 Python 依赖（playwright、pyyaml）"
    "$PIP" install -q -r requirements.txt
    touch .venv/.wificauc_deps_ok
  else
    warn "缺少 playwright/pyyaml，且当前无外网。"
    warn "请先在有外网时执行: ./setup.sh"
    exit 1
  fi
fi

# ---------- wificauc 代码（走 src/，不 pip install -e，避免离线访问 PyPI）----------
if ! "$PYTHON" -c "import wificauc" 2>/dev/null; then
  warn "无法加载 wificauc（检查 ${ROOT}/src/wificauc 是否存在）"
  exit 1
fi

# ---------- Playwright Chromium ----------
if [[ -f .venv/.wificauc_playwright_ok ]]; then
  :
elif "$PYTHON" -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); p.chromium.launch(headless=True).close(); p.stop()" 2>/dev/null; then
  touch .venv/.wificauc_playwright_ok
else
  if has_internet; then
    log "安装 Playwright Chromium（仅首次较慢）"
    "${ROOT}/.venv/bin/playwright" install chromium
    touch .venv/.wificauc_playwright_ok
  else
    warn "Chromium 未就绪且无外网。请先连网执行: ./setup.sh"
    exit 1
  fi
fi

# ---------- 配置文件 ----------
if [[ ! -f config.local.yaml ]]; then
  if [[ -f config.example.yaml ]]; then
    log "生成 config.local.yaml（请随后填写账号密码）"
    cp config.example.yaml config.local.yaml
    chmod 600 config.local.yaml
    warn "请编辑 config.local.yaml 填入 credentials 后重新运行 ./start.sh"
    exit 1
  else
    warn "缺少 config.example.yaml"
    exit 1
  fi
fi

# ---------- 运行 ----------
CMD="${1:-once}"
case "$CMD" in
  check)
    log "仅检测网络/门户（不登录）"
    WIFICAUC_SKIP_LOGIN=1 "$PYTHON" -m wificauc.main once
    ;;
  test)
    log "运行自动化测试"
    env -u WIFICAUC_SKIP_LOGIN ./scripts/accept-m03.sh
    ;;
  force)
    log "强制尝试门户登录（跳过「已上网」检测）"
    echo ""
    "$PYTHON" -m wificauc.main once --force
    ;;
  once|"")
    log "开始：检测 WiFi / 门户，需要时自动登录"
    echo ""
    "$PYTHON" -m wificauc.main once
    ;;
  *)
    warn "未知参数: $CMD"
    echo "用法: $0 [once|check|force|test]"
    exit 1
    ;;
esac

echo ""
printf "${GREEN}完成。${NC}\n"
