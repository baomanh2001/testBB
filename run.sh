#!/usr/bin/env bash
# Cài đặt nhanh + chạy thử
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r requirements.txt
fi

./.venv/bin/python -m bienban fill samples/e-green-01112026.json -o output
echo
echo "Mở web UI:  ./.venv/bin/python web/app.py"
