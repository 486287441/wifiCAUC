#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
pip install -q -e .
export PYTHONPATH="${PWD}/src${PYTHONPATH:+:}"
python -m unittest discover -s tests -p 'test_*.py' -v
