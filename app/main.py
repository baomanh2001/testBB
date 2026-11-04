import io
import os
import urllib.parse
import zipfile
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.docx_generator import generate_report_docx
from app.sample_data import SAMPLE_IMAGES, get_sample_batch
from app.schemas import BatchExportRequest, ReportDocumentRequest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(
    title="Toàn Cầu - Hệ thống Đọc Ảnh Biên Bản & Xuất Word Tự Động",
    version="1.0.0",
)

# Allow all hosts and origins so Arena Live Preview (*.e2b.app) and local LAN work seamlessly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _content_disposition_attachment(filename: str) -> str:
    ascii_fallback = filename.encode("ascii", "ignore").decode("ascii").strip() or "bien_ban.docx"
    ascii_fallback = ascii_fallback.replace('"', "")
    utf8_quoted = urllib.parse.quote(filename, safe="")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{utf8_quoted}"


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "supported_templates": [
            {"id": "mba_1p", "name": "Máy biến áp 1 pha (MBA 1P)"},
            {"id": "mccb", "name": "Máy cắt hạ thế (MCCB)"},
            {"id": "la", "name": "Chống sét van (LA)"},
            {"id": "fco", "name": "Cầu chì tự rơi (FCO)"},
            {"id": "dtnd", "name": "Điện trở nối đất (ĐTNĐ)"},
        ],
    }


@app.get("/api/samples")
def api_samples() -> dict:
    return get_sample_batch()


@app.get("/api/sample-images/{filename}")
def api_sample_image(filename: str) -> FileResponse:
    allowed = set(SAMPLE_IMAGES.values())
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="Sample image not found")
    full_path = os.path.join(BASE_DIR, filename)
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="Sample image missing on disk")
    return FileResponse(full_path, media_type="image/jpeg")


@app.post("/api/export/docx")
def export_single_docx(req: ReportDocumentRequest) -> Response:
    try:
        docx_bytes = generate_report_docx(req)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Lỗi tạo file Word: {exc}") from exc

    fname = (req.filename or "bien_ban.docx").strip()
    if not fname.lower().endswith(".docx"):
        if fname.lower().endswith(".doc"):
            fname = fname[:-4] + ".docx"
        else:
            fname = fname + ".docx"

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": _content_disposition_attachment(fname)},
    )


@app.post("/api/export/zip")
def export_batch_zip(batch: BatchExportRequest) -> Response:
    if not batch.reports:
        raise HTTPException(status_code=400, detail="Danh sách biên bản trống")

    zip_buf = io.BytesIO()
    used_names: set[str] = set()

    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, rep in enumerate(batch.reports, start=1):
            docx_bytes = generate_report_docx(rep)
            fname = (rep.filename or f"{idx:02d}_bien_ban.docx").strip()
            if not fname.lower().endswith(".docx"):
                fname = (fname[:-4] if fname.lower().endswith(".doc") else fname) + ".docx"

            base, ext = os.path.splitext(fname)
            candidate = fname
            counter = 2
            while candidate in used_names:
                candidate = f"{base} ({counter}){ext}"
                counter += 1
            used_names.add(candidate)
            zf.writestr(candidate, docx_bytes)

    zip_name = (batch.zip_filename or "Ho_so_kiem_dinh_Toan_Cau.zip").strip()
    if not zip_name.lower().endswith(".zip"):
        zip_name += ".zip"

    return Response(
        content=zip_buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": _content_disposition_attachment(zip_name)},
    )
