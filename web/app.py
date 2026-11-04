"""Web UI: ảnh → Gemini đọc → sửa → xem trước → tải file .docx.

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
import os
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

from bienban import vision                               # noqa: E402
from bienban.fill import load_config, render_all          # noqa: E402
from bienban.preview import PAGE_CSS, docx_to_html        # noqa: E402
from bienban import checks  # noqa: E402
from bienban.schema import merge_results, web_schema      # noqa: E402
from bienban.spec import DATA_KEYS, TEMPLATES, TITLES     # noqa: E402
from bienban.validate import validate                     # noqa: E402

# Thư mục lưu tạm các file đã sinh (để link tải hoạt động nhiều lần)
STORE = Path(tempfile.gettempdir()) / "bienban-web"
STORE.mkdir(parents=True, exist_ok=True)
STORE_TTL = 60 * 60 * 6          # dọn file cũ sau 6 giờ

app = Flask(__name__, template_folder=str(ROOT / "web" / "templates"))
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024   # ảnh điện thoại
# Sửa template là thấy ngay, không phải khởi động lại server
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True

SAMPLE = ROOT / "samples" / "e-green-01112026.json"


_LOGO_CACHE = ""            # cache data-URI logo công ty


_WM_LOGO: bytes | None = None


def _watermark_css() -> str:
    """CSS để bản xem trước trên web có đúng dấu chìm như bản in."""
    global _WM_LOGO
    if _WM_LOGO is None:
        try:
            import docx

            from bienban.watermark import find_logo

            _WM_LOGO = find_logo(docx.Document(str(ROOT / "templates" / TEMPLATES["45"]))) or b""
        except Exception:                                  # pragma: no cover
            _WM_LOGO = b""
    if not _WM_LOGO:
        return ""
    import base64

    b64 = base64.b64encode(_WM_LOGO).decode()
    mime = "image/png" if _WM_LOGO[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return ("\n.page-wm::before{background-image:url(data:%s;base64,%s)}\n" % (mime, b64))


def _brand_logo() -> str:
    """Logo công ty (lấy từ file mẫu Word) dạng data-URI, cache 1 lần."""
    global _LOGO_CACHE
    if _LOGO_CACHE:
        return _LOGO_CACHE
    try:
        import base64

        import docx

        from bienban.watermark import find_logo

        doc = docx.Document(str(ROOT / "templates" / TEMPLATES["45"]))
        blob = find_logo(doc)
        if blob:
            from bienban.watermark import _shrink

            blob = _shrink(blob, 96, target_px=256)   # logo trên web chỉ cần nhỏ
            mime = "image/png" if blob[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
            _LOGO_CACHE = f"data:{mime};base64," + base64.b64encode(blob).decode()
    except Exception:                                     # pragma: no cover
        _LOGO_CACHE = ""
        return ""
    return _LOGO_CACHE


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


def _gemini_key() -> str | None:
    """Key do người dùng nhập (header) hoặc trong biến môi trường; không lưu lại."""
    return (request.headers.get("X-Gemini-Key") or "").strip() or None


# --------------------------------------------------------------------------- #
# API: nhận dạng ảnh bằng Gemini
# --------------------------------------------------------------------------- #
@app.get("/api/ai/schema")
def api_ai_schema():
    return jsonify({
        "ok": True,
        "schema": web_schema(),
        "forms": [{"key": k, "title": TITLES[k], "data_key": DATA_KEYS[k]}
                  for k in sorted(TEMPLATES)],
        "has_env_key": bool(os.environ.get("GEMINI_API_KEY")),
        "default_model": vision.DEFAULT_MODEL,
        "max_images": vision.MAX_IMAGES,
    })


@app.get("/api/ai/prompt")
def api_ai_prompt():
    """Prompt thật sẽ gửi Gemini – để người dùng đọc/kiểm tra."""
    forms = [f for f in (request.args.get("forms") or "").split(",") if f in TEMPLATES] or None
    return jsonify({"ok": True, "prompt": vision.build_prompt(forms)})


@app.get("/api/ai/status")
def api_ai_status():
    """Cho giao diện biết đã có key trên server chưa (không trả key)."""
    has = bool(os.environ.get("GEMINI_API_KEY"))
    return jsonify({"ok": True, "has_env_key": has,
                    "default_model": vision.DEFAULT_MODEL,
                    "max_images": vision.MAX_IMAGES,
                    "hint": ("Server đã có GEMINI_API_KEY - không cần nhập key."
                             if has else
                             "Chưa có key: nhập trên giao diện hoặc đặt "
                             "GEMINI_API_KEY khi chạy server.")})


@app.get("/api/ai/models")
def api_ai_models():
    """Danh sách model hỗ trợ generateContent (cho dropdown)."""
    try:
        models = vision.list_models(_gemini_key())
    except vision.GeminiError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if not models:
        models = [vision.auto_model(_gemini_key())]
    return jsonify({"ok": True, "models": models,
                    "default": models[0], "selected": models[0]})


# Ảnh của lần nhận dạng gần nhất, giữ trong RAM (không ghi ra đĩa) để bước
# "soát lại bằng AI" dùng lại chính các ảnh đó mà không phải upload lại.
_LAST_IMAGES: dict = {"blobs": [], "sizes": []}
_MAX_CACHE_BYTES = 24 * 1024 * 1024          # 24 MB
_MAX_CACHE_IMAGES = 8


def _env_list(name: str) -> list[str]:
    """Đọc danh sách phân tách bằng dấu phẩy trong biến môi trường."""
    raw = os.environ.get(name) or ""
    return [x.strip() for x in raw.split(",") if x.strip()]


def _remember_images(blobs: list[bytes]) -> None:
    keep, total = [], 0
    for b in blobs[:_MAX_CACHE_IMAGES]:
        if total + len(b) > _MAX_CACHE_BYTES:
            break
        keep.append(b)
        total += len(b)
    _LAST_IMAGES["blobs"] = keep
    _LAST_IMAGES["sizes"] = [len(b) for b in keep]


def _last_blobs() -> list[bytes]:
    return list(_LAST_IMAGES.get("blobs") or [])


@app.post("/api/check")
def api_check():
    """Soát số liệu sau khi AI đọc ảnh — trả về "log nhỏ" cảnh báo.

    Mặc định chỉ chạy lớp quy tắc (không gọi mạng, tức thì). Thêm ``ai=1`` để
    hỏi lại model với chính các ảnh vừa dùng (tuỳ chọn, chậm hơn 10–30 giây).
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "JSON không hợp lệ"}), 400

    warnings_ = checks.check_rules(data)
    out = [w.as_dict() for w in warnings_]
    ai_error = None
    if request.args.get("ai") in ("1", "true", "yes"):
        try:
            blobs = _last_blobs()
            if blobs:
                forms = [f for f in (request.args.get("forms") or "").split(",")
                         if f in TEMPLATES] or None
                ai_warn = checks.check_with_ai(
                    data, blobs[:8], key=_gemini_key(),
                    model=request.args.get("model") or None, forms=forms)
                out += [w.as_dict() for w in ai_warn]
        except vision.GeminiError as exc:
            ai_error = str(exc)
        except Exception as exc:                              # pragma: no cover
            app.logger.exception("ai check failed")
            ai_error = f"Lỗi khi soát bằng AI: {exc}"
    return jsonify({
        "ok": True,
        "checks": out,
        "ai_error": ai_error,
        "counts": {"rule": sum(1 for c in out if c["source"] == "rule"),
                   "ai": sum(1 for c in out if c["source"] == "ai")},
    })


@app.post("/api/merge")
def api_merge():
    """Gộp kết quả nhận dạng của nhiều nhóm ảnh → một bộ biên bản.

    Body: ``{"results": [ {...}, {...} ]}`` (mỗi phần tử là ``data`` của một
    lần gọi ``/api/ai/recognize``). Trả về dữ liệu đã gộp + ghi chú gộp.
    """
    body = request.get_json(silent=True) or {}
    results = body.get("results")
    if not isinstance(results, list) or not results:
        return jsonify({"ok": False, "error": "Thiếu danh sách kết quả để gộp"}), 400
    data, notes = merge_results(results)
    if not any(k in data for k in DATA_KEYS.values()):
        return jsonify({"ok": False, "error": "Không có biên bản nào trong dữ liệu gộp"}), 422
    return jsonify({"ok": True, "data": data, "notes": notes,
                    "blocks": [k for k in DATA_KEYS.values() if k in data],
                    "problems": _problems_json(validate(data))})


@app.post("/api/ai/recognize")
def api_ai_recognize():
    """Nhận ảnh biên bản → JSON đã chuẩn hoá theo đúng cấu trúc của tool."""
    uploads = [f for f in request.files.getlist("images") if f and f.filename]
    if not uploads:
        return jsonify({"ok": False, "error": "Chưa chọn ảnh nào"}), 400
    if len(uploads) > vision.MAX_IMAGES:
        return jsonify({"ok": False,
                        "error": f"Chỉ gửi tối đa {vision.MAX_IMAGES} ảnh mỗi lần"}), 400
    blobs = [f.read() for f in uploads]
    if any(not b for b in blobs):
        return jsonify({"ok": False, "error": "Có ảnh rỗng hoặc đọc lỗi"}), 400
    _remember_images(blobs)      # để bước soát AI dùng lại, không cần upload lại

    forms = [f for f in (request.form.get("forms") or "").split(",") if f]
    forms = [f for f in forms if f in TEMPLATES] or None
    cfg0 = load_config().get("ai") or {}
    model = ((request.form.get("model") or "").strip()
             or (cfg0.get("default_model") or "").strip()
             or None)                                   # None = tự dò theo key

    try:
        cfg_ai = load_config().get("ai") or {}
        tried: list[str] = []
        raw = vision.call_gemini(
            blobs, key=_gemini_key(), model=model, forms=forms,
            fallbacks=cfg_ai.get("fallback_models") or _env_list("GEMINI_FALLBACK_MODELS"),
            alt_keys=cfg_ai.get("fallback_keys") or _env_list("GEMINI_API_KEYS")[1:],
            on_try=lambda i, m, slot, exc: tried.append(f"{m} (key {slot}): {exc}"))
        data = vision.normalize_ai_result(raw, forms=forms)
    except vision.GeminiError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:                                  # pragma: no cover
        app.logger.exception("gemini failed")
        return jsonify({"ok": False, "error": f"Lỗi khi gọi Gemini: {exc}"}), 500

    if not any(k in data for k in DATA_KEYS.values()):
        return jsonify({
            "ok": False,
            "error": "Gemini không nhận ra biên bản nào trong ảnh. Thử ảnh rõ hơn "
                     "hoặc chọn đúng mẫu cần nhận dạng.",
            "notes": data.get("_ai", {}).get("notes", []),
            "raw": raw,
        }), 422

    problems = validate(data)
    return jsonify({
        "ok": True,
        "data": data,
        "model": model,
        "notes": data.get("_ai", {}).get("notes", []),
        "sources": data.get("_ai", {}).get("sources", {}),
        "blocks": [k for k in DATA_KEYS.values() if k in data],
        "problems": _problems_json(problems),
        # cảnh báo quy tắc ngay sau khi đọc ảnh (lớp AI là tuỳ chọn, gọi /api/check?ai=1)
        "checks": [w.as_dict() for w in checks.check_rules(data)],
        # nếu phải chuyển phương án, nói rõ cho người dùng biết
        "fallback": tried,
    })


@app.post("/api/normalize")
def api_normalize():
    """Chuyển JSON bất kỳ (kể cả JSON do AI trả về) về cấu trúc chuẩn của tool."""
    raw = request.get_json(silent=True)
    if not isinstance(raw, dict):
        return jsonify({"ok": False, "error": "JSON không hợp lệ"}), 400
    reports = raw.get("reports")
    if not isinstance(reports, list):
        reports = [{"report_type": f, "data": raw[DATA_KEYS[f]]}
                   for f in sorted(TEMPLATES) if isinstance(raw.get(DATA_KEYS[f]), dict)]
    data = vision.normalize_ai_result({
        "thong_tin_chung": raw.get("thong_tin_chung") or {},
        "reports": reports,
        "context_photos": raw.get("_ai", {}).get("context", []) if isinstance(raw.get("_ai"), dict) else [],
    })
    return jsonify({"ok": True, "data": data})


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
        schema=web_schema(),
        logo=_brand_logo(),
        css=PAGE_CSS + _watermark_css(),
        default_model=vision.DEFAULT_MODEL,
        max_images=vision.MAX_IMAGES,
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
        css=PAGE_CSS + _watermark_css(),
        body=docx_to_html(target),
        name=name,
        download_url=f"/download/{token}/{name}",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)
