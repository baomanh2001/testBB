#!/usr/bin/env bash
# Kiểm tra nhanh môi trường (không mở server) — tiện khi có trục trặc.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x ".venv/bin/python" ]; then
  echo "Chưa có môi trường. Hãy chạy ./chay-web.sh trước."
  exit 1
fi
exec ./.venv/bin/python launcher.py --check
