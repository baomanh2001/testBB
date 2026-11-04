"""Khởi động web UI bằng một lệnh — không phải gõ lại gì.

Được gọi tự động bởi ``Chay-Web.bat`` (Windows) và ``chay-web.sh``
(macOS/Linux), nhưng chạy tay cũng được::

    python launcher.py                # mở trình duyệt, cổng 8000
    python launcher.py --port 8090
    python launcher.py --no-browser
    python launcher.py --check        # kiểm tra môi trường rồi thoát

Việc nó tự làm:

1. Đọc ``.env`` cạnh file này (nếu có) và nạp ``GEMINI_API_KEY``.
2. Chưa có key mà chạy trong terminal → hỏi một lần rồi **lưu vào ``.env``**
   (file đã nằm trong ``.gitignore``, không bị commit, không gửi lên mạng).
3. Tìm cổng trống (8000, 8001, …) nếu cổng mặc định đang bận.
4. Bật server và tự mở trình duyệt.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
DEFAULT_PORT = 8000

BANNER = "\033[1;36m" if os.name != "nt" else ""
RESET = "\033[0m" if os.name != "nt" else ""


# --------------------------------------------------------------------------- #
# .env
# --------------------------------------------------------------------------- #
def read_env(path: Path = ENV_FILE) -> dict[str, str]:
    """Đọc file .env kiểu đơn giản (KEY=VALUE, cho phép dấu nháy và #)."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        if key.strip():
            out[key.strip()] = value
    return out


def write_env(key: str, value: str, path: Path = ENV_FILE) -> None:
    """Ghi/ghi đè một khoá trong .env, giữ nguyên các khoá khác."""
    values = read_env(path)
    values[key] = value
    lines = [
        "# File cấu hình riêng của máy này — KHÔNG commit (đã có trong .gitignore).",
        "# Sinh tự động bởi launcher.py; sửa tay cũng được.",
        "",
    ]
    for k, v in values.items():
        lines.append(f"{k}={v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:                                    # ai cũng đọc được file thì hơi rủi ro
        os.chmod(path, 0o600)
    except OSError:
        pass


def apply_env(path: Path | None = None) -> dict[str, str]:
    """Nạp .env vào biến môi trường (không ghi đè biến đã có sẵn)."""
    values = read_env(path or ENV_FILE)
    for k, v in values.items():
        os.environ.setdefault(k, v)
    return values


# --------------------------------------------------------------------------- #
# Cổng
# --------------------------------------------------------------------------- #
def port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def pick_port(start: int, tries: int = 20) -> int:
    for port in range(start, start + tries):
        if port_free(port):
            return port
    raise SystemExit(
        f"Không tìm được cổng trống trong khoảng {start}–{start + tries - 1}.\n"
        f"Thử: python launcher.py --port 9000"
    )


# --------------------------------------------------------------------------- #
# Kiểm tra môi trường
# --------------------------------------------------------------------------- #
def requirements_missing() -> list[str]:
    missing = []
    for mod, pkg in (("docx", "python-docx"), ("lxml", "lxml"), ("flask", "Flask")):
        try:
            __import__(mod)
        except Exception:
            missing.append(pkg)
    return missing


def check() -> int:
    ok = True
    print(f"{BANNER}== Kiểm tra môi trường =={RESET}")
    print(f"  Python        : {sys.version.split()[0]}  ({sys.executable})")

    missing = requirements_missing()
    if missing:
        ok = False
        print(f"  Thư viện      : THIẾU {', '.join(missing)}")
        print("                  → chạy lại bằng file .bat/.sh để tự cài")
    else:
        print("  Thư viện      : đủ (python-docx, lxml, Flask)")

    templates = sorted((ROOT / "templates").glob("*.docx"))
    print(f"  Mẫu Word      : {len(templates)}/5 file")
    ok = ok and len(templates) >= 5

    key = os.environ.get("GEMINI_API_KEY") or read_env().get("GEMINI_API_KEY")
    print(f"  API key Gemini: {'đã có' if key else 'chưa có (nhập sau khi chạy, hoặc dán vào .env)'}")
    print(f"  File .env     : {'có' if ENV_FILE.exists() else 'chưa có (sẽ tạo khi bạn nhập key)'}")
    print(f"  Cổng {DEFAULT_PORT}      : {'trống' if port_free(DEFAULT_PORT) else 'đang bận → sẽ tự dùng cổng khác'}")
    print(f"{BANNER}== {'OK' if ok else 'CÓ LỖI'} =={RESET}")
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# Hỏi key (chỉ khi chạy trong terminal)
# --------------------------------------------------------------------------- #
def ask_key_if_needed() -> None:
    if os.environ.get("GEMINI_API_KEY", "").strip():
        return
    if not sys.stdin.isatty():
        return
    print()
    print("Chưa có API key Gemini — bỏ trống vẫn dùng được (dán key trên web,")
    print("hoặc nhập JSON tay), chỉ là không nhận dạng ảnh được.")
    print("Lấy key miễn phí: https://aistudio.google.com/apikey")
    try:
        key = input("Dán API key Gemini (Enter để bỏ qua): ").strip()
    except (EOFError, KeyboardInterrupt):
        key = ""
    if key:
        os.environ["GEMINI_API_KEY"] = key
        write_env("GEMINI_API_KEY", key)
        print(f"✓ Đã lưu vào {ENV_FILE.name} — lần sau khỏi nhập lại.")
    else:
        print("→ Bỏ qua. Có thể nhập sau trên giao diện.")


# --------------------------------------------------------------------------- #
# Chạy
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Chạy web UI điền biên bản 44–48")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", DEFAULT_PORT)))
    ap.add_argument("--host", default="0.0.0.0", help="mặc định 0.0.0.0 (vào được từ máy khác)")
    ap.add_argument("--no-browser", action="store_true", help="không tự mở trình duyệt")
    ap.add_argument("--check", action="store_true", help="kiểm tra môi trường rồi thoát")
    ap.add_argument("--no-key-prompt", action="store_true", help="không hỏi API key")
    args = ap.parse_args()

    apply_env()

    if args.check:
        return check()

    missing = requirements_missing()
    if missing:
        print(f"Thiếu thư viện: {', '.join(missing)}", file=sys.stderr)
        print("Chạy bằng file Chay-Web.bat (Windows) hoặc ./chay-web.sh để tự cài.",
              file=sys.stderr)
        return 1

    if not args.no_key_prompt:
        ask_key_if_needed()

    port = pick_port(args.port)
    url = f"http://127.0.0.1:{port}"

    sys.path.insert(0, str(ROOT))
    from web.app import app            # noqa: E402  (cần đường dẫn ở trên)

    if port != args.port:
        print(f"(!) Cổng {args.port} đang bận → dùng cổng {port}")

    print()
    print(f"{BANNER}══════════════════════════════════════════════════════════{RESET}")
    print(f"{BANNER}  BIÊN BẢN KIỂM ĐỊNH 44–48 — đang chạy{RESET}")
    print(f"  Mở trên máy này : {url}")
    print(f"  Điện thoại/máy khác (cùng wifi): http://<IP-máy-tính>:{port}")
    key_state = "đã có" if os.environ.get("GEMINI_API_KEY") else "chưa có (dán trên web)"
    print(f"  API key Gemini  : {key_state}")
    print("  Dừng server     : Ctrl + C  (hoặc đóng cửa sổ này)")
    print(f"{BANNER}══════════════════════════════════════════════════════════{RESET}")
    print()

    if not args.no_browser:
        def open_later():
            time.sleep(1.6)
            try:
                webbrowser.open(url)
            except Exception:
                pass

        threading.Thread(target=open_later, daemon=True).start()

    try:
        app.run(host=args.host, port=port, debug=False, threaded=True,
                use_reloader=False)
    except KeyboardInterrupt:
        print("\nĐã dừng.")
    except OSError as exc:
        print(f"\nKhông mở được cổng {port}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
