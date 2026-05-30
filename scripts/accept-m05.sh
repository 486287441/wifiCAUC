#!/usr/bin/env bash
# M05 自动化验收：单元测试 + LaunchAgent 文件检查
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
pip install -q -e . -q

echo "== 1/2 单元测试 test_m05 =="
python -m unittest tests.test_m05 -v

echo ""
echo "== 2/2 LaunchAgent 模板与脚本 =="
for f in launchd/com.wificauc.agent.plist.template \
  scripts/install-launchagent.sh \
  scripts/uninstall-launchagent.sh; do
  [[ -f "$f" ]] || { echo "FAIL: missing $f" >&2; exit 1; }
  echo "  OK $f"
done

grep -q '{{VENV_PYTHON}}' launchd/com.wificauc.agent.plist.template
grep -q 'wificauc.main' launchd/com.wificauc.agent.plist.template
grep -q 'KeepAlive' launchd/com.wificauc.agent.plist.template
[[ -x scripts/install-launchagent.sh ]]
[[ -x scripts/uninstall-launchagent.sh ]]

echo ""
echo "M05 自动化验收通过。"
echo "本机可选：./scripts/install-launchagent.sh 后 launchctl kickstart gui/\$(id -u)/com.wificauc.agent"
