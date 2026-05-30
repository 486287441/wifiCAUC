#!/usr/bin/env bash
# 安装 wifiCAUC LaunchAgent（登录后常驻轮询）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LABEL="com.wificauc.agent"
PLIST_NAME="${LABEL}.plist"
TEMPLATE="${ROOT}/launchd/com.wificauc.agent.plist.template"
DEST="${HOME}/Library/LaunchAgents/${PLIST_NAME}"
VENV_PYTHON="${ROOT}/.venv/bin/python"
LOG_DIR="${HOME}/Library/Logs/wifiCAUC"

die() {
  echo "错误: $*" >&2
  exit 1
}

[[ -x "$VENV_PYTHON" ]] || die "未找到 ${VENV_PYTHON}，请先在本目录执行 ./setup.sh"
[[ -f config.local.yaml ]] || die "未找到 config.local.yaml，请先 cp config.example.yaml config.local.yaml 并填写账号密码"
[[ -f "$TEMPLATE" ]] || die "缺少模板 ${TEMPLATE}"

if ! "$VENV_PYTHON" -c "import wificauc" 2>/dev/null; then
  echo "==> 安装 wificauc 到虚拟环境（pip install -e .）"
  "${ROOT}/.venv/bin/pip" install -q -e .
fi

mkdir -p "${LOG_DIR}"
mkdir -p "${HOME}/Library/LaunchAgents"

echo "==> 生成 ${DEST}"
sed \
  -e "s|{{VENV_PYTHON}}|${VENV_PYTHON}|g" \
  -e "s|{{PROJECT_ROOT}}|${ROOT}|g" \
  -e "s|{{LOG_DIR}}|${LOG_DIR}|g" \
  "$TEMPLATE" >"$DEST"

UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}"

if launchctl print "${DOMAIN}/${LABEL}" &>/dev/null; then
  echo "==> 卸载旧版 Agent"
  launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || launchctl unload -w "$DEST" 2>/dev/null || true
fi

echo "==> 加载 LaunchAgent"
if launchctl bootstrap "$DOMAIN" "$DEST" 2>/dev/null; then
  :
else
  launchctl load -w "$DEST"
fi

echo ""
echo "已安装 LaunchAgent：${LABEL}"
echo "  日志 stdout: ${LOG_DIR}/agent.log"
echo "  日志 stderr: ${LOG_DIR}/agent.err.log"
echo ""
echo "常用命令："
echo "  tail -f ${LOG_DIR}/agent.log"
echo "  ${VENV_PYTHON} -m wificauc.main status"
echo "  launchctl kickstart -k ${DOMAIN}/${LABEL}   # 立即跑一轮"
echo "  ./scripts/uninstall-launchagent.sh"
