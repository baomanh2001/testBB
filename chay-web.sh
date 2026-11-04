#!/usr/bin/env bash
# Bấm đúp (macOS) hoặc ./chay-web.sh (Linux/macOS) là chạy.
# Lần đầu sẽ tự tạo môi trường + cài thư viện + hỏi API key 1 lần.
set -euo pipefail
cd "$(dirname "$0")"

echo
echo "============================================================"
echo "  BIÊN BẢN KIỂM ĐỊNH ĐIỆN LỰC 44–48"
echo "  Lần đầu chạy sẽ tự cài môi trường, hỏi API key 1 lần."
echo "============================================================"
echo

# ---- 1) Tìm Python -----------------------------------------------------
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then
    if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      PY="$c"; break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo "✗ Không tìm thấy Python 3.10+."
  echo "  macOS : brew install python@3.12    (hoặc tải tại python.org)"
  echo "  Ubuntu: sudo apt install python3 python3-venv python3-pip"
  exit 1
fi

# ---- 2) Môi trường -----------------------------------------------------
# Dùng .venv trong thư mục này; nếu chưa có mà máy đã có sẵn python đủ thư
# viện thì dùng luôn cho nhanh (khỏi tạo 80 MB).
if [ -x ".venv/bin/python" ]; then
  VPY=".venv/bin/python"
elif "$PY" -c 'import docx, lxml, flask' >/dev/null 2>&1; then
  VPY="$PY"
  echo "[1/3] Dùng Python sẵn có (đã đủ thư viện), không tạo .venv."
else
  echo "[1/3] Đang tạo môi trường Python .venv …"
  "$PY" -m venv .venv
  VPY=".venv/bin/python"
fi

# ---- 3) Thư viện -------------------------------------------------------
if ! "$VPY" -c 'import docx, lxml, flask' >/dev/null 2>&1; then
  echo "[2/3] Đang cài thư viện (lần đầu, 1–3 phút) …"
  "$VPY" -m pip install --upgrade pip --quiet
  "$VPY" -m pip install --quiet -r requirements.txt || {
    echo "✗ Cài thư viện thất bại. Kiểm tra kết nối mạng rồi chạy lại."
    exit 1
  }
else
  echo "[2/3] Thư viện đã đủ."
fi

# ---- 4) Chạy -----------------------------------------------------------
echo "[3/3] Đang mở web …  (Ctrl+C để dừng)"
echo
exec "$VPY" launcher.py --port "${PORT:-8000}"
