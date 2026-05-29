#!/usr/bin/env bash
# M03 自动化验收：单元测试 + 可选真实登录（需 CAUC 网络）
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
playwright install chromium 2>/dev/null || true

echo "== M03 单元测试 =="
python -m unittest tests.test_m03 -v

echo ""
echo "== M02 回归（mock 登录） =="
env -u WIFICAUC_SKIP_LOGIN ./scripts/accept-m02.sh

if [[ "${WIFICAUC_LIVE_LOGIN:-}" == "1" ]]; then
  echo ""
  echo "== 真实门户登录 =="
  python -m wificauc.main once
else
  echo ""
  echo "跳过真实登录。在校园网下执行: WIFICAUC_LIVE_LOGIN=1 $0"
fi

echo ""
echo "M03 自动化验收通过。"
