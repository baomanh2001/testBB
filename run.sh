#!/usr/bin/env bash
set -e

if [ ! -d ".venv" ]; then
  echo "[1/3] Đang tạo môi trường ảo .venv..."
  python3 -m venv .venv
fi

echo "[2/3] Đang cài đặt thư viện..."
.venv/bin/pip install -q -r requirements.txt

echo "[3/3] Khởi động Web Server tại http://0.0.0.0:8000 ..."
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
