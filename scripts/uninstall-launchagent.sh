#!/usr/bin/env bash
# 卸载 wifiCAUC LaunchAgent
set -euo pipefail

LABEL="com.wificauc.agent"
PLIST_NAME="${LABEL}.plist"
DEST="${HOME}/Library/LaunchAgents/${PLIST_NAME}"
UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}"

if [[ -f "$DEST" ]]; then
  echo "==> 停止并卸载 ${LABEL}"
  launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || launchctl unload -w "$DEST" 2>/dev/null || true
  rm -f "$DEST"
  echo "已删除 ${DEST}"
else
  echo "未找到 ${DEST}，尝试 bootout..."
  launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true
fi

echo "LaunchAgent 已卸载。日志仍保留在 ~/Library/Logs/wifiCAUC/"
