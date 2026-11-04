"""Web UI: dán JSON → xem trước → tải 5 file .docx.

Chạy local::

    python web/app.py                 # http://127.0.0.1:8000
    PORT=8080 python web/app.py

Không cần Node, không cần build. Toàn bộ xử lý diễn ra trên máy chủ chạy
Flask; trình duyệt chỉ gửi JSON và tải file về.
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bienban.fill import load_config, render_all          # noqa: E402
from bienban.spec import DATA_KEYS, TEMPLATES, TITLES     # noqa: E402
from bienban.validate import validate                     # noqa: E402

app = Flask(__name__, template_folder=str(ROOT / "web" / "templates"))
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024

SAMPLE = ROOT / "samples" / "e-green-01112026.json"


@app.get("/")
def index():
    return render_template(
        "index.html",
        sample=SAMPLE.read_text(encoding="utf-8"),
        forms=[{"key": k, "title": TITLES[k], "file": TEMPLATES[k]} for k in sorted(TEMPLATES)],
    )


@app.post("/api/validate")
def api_validate():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "JSON không hợp lệ"}), 400
    problems = validate(data)
    return jsonify(
        {
            "ok": not any(p.level == "error" for p in problems),
            "problems": [{"level": p.level, "where": p.where, "message": p.message} for p in problems],
            "forms": [k for k in sorted(TEMPLATES) if DATA_KEYS[k] in data],
        }
    )


def _render(data: dict) -> tuple[dict[str, bytes], list[str]]:
    import tempfile

    cfg = load_config()
    with tempfile.TemporaryDirectory() as tmp:
        paths, warnings = render_all(
            data, templates_dir=ROOT / "templates", out_dir=tmp, cfg=cfg
        )
        files = {Path(p).name: Path(p).read_bytes() for p in paths}
    return files, warnings


@app.post("/api/render")
def api_render():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "JSON không hợp lệ"}), 400
    problems = validate(data)
    if any(p.level == "error" for p in problems):
        return jsonify({
            "ok": False,
            "error": "Dữ liệu còn lỗi, chưa thể sinh biên bản",
            "problems": [{"level": p.level, "where": p.where, "message": p.message}
                         for p in problems],
        }), 400
    try:
        files, warnings = _render(data)
    except Exception as exc:  # pragma: no cover - phản hồi lỗi cho UI
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({
        "ok": True,
        "files": list(files),
        "warnings": warnings,
        "problems": [{"level": p.level, "where": p.where, "message": p.message}
                     for p in problems],
    })


@app.post("/api/download")
def api_download():
    data = request.get_json(silent=True) or {}
    payload = data.get("data")
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "Thiếu dữ liệu"}), 400
    files, _ = _render(payload)
    only = data.get("name")
    if only:
        files = {k: v for k, v in files.items() if k == only}
    if not files:
        return jsonify({"ok": False, "error": "Không có biên bản nào để tải"}), 400
    if len(files) == 1:
        name, blob = next(iter(files.items()))
        return send_file(io.BytesIO(blob), as_attachment=True, download_name=name,
                         mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, blob in files.items():
            zf.writestr(name, blob)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="bien-ban-kdm.zip",
                     mimetype="application/zip")


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)
