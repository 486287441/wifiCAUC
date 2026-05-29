#!/usr/bin/env bash
# 在有外网时运行一次：装齐依赖与 Chromium；注销后 ./start.sh 不再访问 PyPI
set -euo pipefail
cd "$(dirname "$0")"

export PYTHONPATH="${PWD}/src${PYTHONPATH:+:}"

echo "==> 创建虚拟环境"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> 升级 pip"
pip install --upgrade pip -q

echo "==> 安装 playwright、pyyaml"
pip install -r requirements.txt

echo "==> 校验 wificauc 源码可导入"
python -c "import wificauc; print('wificauc', wificauc.__version__)"

echo "==> 安装 Playwright Chromium（约 100MB，仅首次）"
playwright install chromium

touch .venv/.wificauc_deps_ok
touch .venv/.wificauc_playwright_ok

if [[ ! -f config.local.yaml ]] && [[ -f config.example.yaml ]]; then
  cp config.example.yaml config.local.yaml
  chmod 600 config.local.yaml
  echo "==> 已生成 config.local.yaml，请填写账号密码"
fi

echo ""
echo "全部装好。注销门户后在本目录执行: ./start.sh"
echo "（离线只访问 192.168.4.252，不会再连 pypi.org）"
