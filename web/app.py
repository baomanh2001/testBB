"""Web UI: dán JSON → xem trước biên bản → tải file .docx.

Chạy local::

    python web/app.py                 # http://127.0.0.1:8000
    PORT=8080 python web/app.py

Hai điểm quan trọng cho môi trường nhúng iframe (preview của Arena, Zalo,
Facebook…):

1. **Tải file bằng link thật** (``<a href="/download/<id>/<file>">``) chứ
   không dùng ``fetch`` + ``URL.createObjectURL`` — nhiều trình duyệt chặn
   kiểu tải bằng blob trong iframe.
2. **Xem trước ngay trên web** để không cần tải file mới biết nội dung.
"""

from __future__ import annotations

import io
import sys
import tempfile
import time
import uuid
import zipfile
from pathlib import Path

from flask import (Flask, abort, jsonify, render_template, request, send_file,
                   send_from_directory)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bienban.fill import load_config, render_all          # noqa: E402
from bienban.preview import PAGE_CSS, docx_to_html        # noqa: E402
from bienban.spec import DATA_KEYS, TEMPLATES, TITLES     # noqa: E402
from bienban.validate import validate                     # noqa: E402

# Thư mục lưu tạm các file đã sinh (để link tải hoạt động nhiều lần)
STORE = Path(tempfile.gettempdir()) / "bienban-web"
STORE.mkdir(parents=True, exist_ok=True)
STORE_TTL = 60 * 60 * 6          # dọn file cũ sau 6 giờ

app = Flask(__name__, template_folder=str(ROOT / "web" / "templates"))
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024

SAMPLE = ROOT / "samples" / "e-green-01112026.json"


# --------------------------------------------------------------------------- #
# Tiện ích
# --------------------------------------------------------------------------- #
def _cleanup() -> None:
    now = time.time()
    for p in STORE.iterdir():
        try:
            if now - p.stat().st_mtime > STORE_TTL:
                if p.is_dir():
                    for f in p.iterdir():
                        f.unlink(missing_ok=True)
                    p.rmdir()
                else:
                    p.unlink()
        except OSError:
            pass


def _render(data: dict) -> tuple[dict[str, bytes], list[str]]:
    tmp = Path(tempfile.mkdtemp())
    cfg = load_config()
    try:
        paths, warnings = render_all(
            data, templates_dir=ROOT / "templates", out_dir=tmp, cfg=cfg
        )
        return {Path(p).name: Path(p).read_bytes() for p in paths}, warnings
    finally:
        for f in tmp.glob("*"):
            f.unlink(missing_ok=True)
        tmp.rmdir()


def _problems_json(problems) -> list[dict]:
    return [{"level": p.level, "where": p.where, "message": p.message} for p in problems]


# --------------------------------------------------------------------------- #
# Trang
# --------------------------------------------------------------------------- #
@app.get("/")
def index():
    _cleanup()
    return render_template(
        "index.html",
        sample=SAMPLE.read_text(encoding="utf-8"),
        forms=[{"key": k, "title": TITLES[k], "file": TEMPLATES[k],
                "data_key": DATA_KEYS[k]} for k in sorted(TEMPLATES)],
        css=PAGE_CSS,
    )


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
@app.post("/api/validate")
def api_validate():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "JSON không hợp lệ"}), 400
    problems = validate(data)
    return jsonify({
        "ok": not any(p.level == "error" for p in problems),
        "problems": _problems_json(problems),
        "forms": [k for k in sorted(TEMPLATES) if DATA_KEYS[k] in data],
    })


@app.post("/api/render")
def api_render():
    """Sinh biên bản, lưu tạm, trả về id phiên + danh sách file + nội dung xem trước."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "JSON không hợp lệ"}), 400
    problems = validate(data)
    if any(p.level == "error" for p in problems):
        return jsonify({
            "ok": False,
            "error": "Dữ liệu còn lỗi, chưa thể sinh biên bản",
            "problems": _problems_json(problems),
        }), 400
    try:
        files, warnings = _render(data)
    except Exception as exc:  # pragma: no cover
        app.logger.exception("render failed")
        return jsonify({"ok": False, "error": f"Không sinh được biên bản: {exc}"}), 500
    if not files:
        return jsonify({"ok": False, "error": "Không có biên bản nào để sinh"}), 400

    _cleanup()
    token = uuid.uuid4().hex[:12]
    folder = STORE / token
    folder.mkdir(parents=True, exist_ok=True)
    previews: dict[str, str] = {}
    for name, blob in files.items():
        (folder / name).write_bytes(blob)
        try:
            previews[name] = docx_to_html(blob)
        except Exception as exc:  # pragma: no cover
            app.logger.exception("preview failed for %s", name)
            previews[name] = f'<p style="color:#b00">Không dựng được xem trước: {exc}</p>'

    return jsonify({
        "ok": True,
        "token": token,
        "files": list(files),
        "previews": previews,
        "warnings": warnings,
        "problems": _problems_json(problems),
        "zip_url": f"/download/{token}/__all__.zip",
    })


@app.get("/download/<token>/<path:name>")
def download(token: str, name: str):
    """Link tải thật: bấm là trình duyệt tải file, không cần JS."""
    folder = STORE / token
    if not folder.is_dir() or "/" in token or ".." in token:
        abort(404)
    if name == "__all__.zip":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(folder.iterdir()):
                if f.is_file():
                    zf.writestr(f.name, f.read_bytes())
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name="bien-ban-kdm.zip",
                         mimetype="application/zip")
    target = folder / name
    if not target.is_file():
        abort(404)
    return send_from_directory(
        folder, name, as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/preview/<token>/<path:name>")
def preview_page(token: str, name: str):
    """Mở bản xem trước ở tab riêng (in được ra PDF nếu cần)."""
    folder = STORE / token
    target = folder / name
    if not target.is_file():
        abort(404)
    return render_template(
        "preview.html",
        css=PAGE_CSS,
        body=docx_to_html(target),
        name=name,
        download_url=f"/download/{token}/{name}",
    )


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)
