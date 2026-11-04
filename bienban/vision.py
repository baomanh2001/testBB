"""Nhận dạng ảnh biên bản bằng Gemini → JSON đúng cấu trúc của tool.

Module này **chỉ** lo phần giao tiếp với Google Generative Language API và
phần dựng prompt; việc dựng form chỉnh sửa nằm ở web UI, việc điền Word nằm ở
:mod:`bienban.fill`.

Vì sao gọi qua backend (khác với một số bản tham khảo gọi trực tiếp từ
trình duyệt):

* API key **không bao giờ** gửi xuống trình duyệt (không lộ khi chia sẻ link,
  không lọt vào lịch sử/extension của máy người dùng);
* ảnh được nén (``MAX_EDGE``) và gửi 1 lần cho cả lô → ít request hơn;
* có timeout, thử lại và thông báo lỗi tiếng Việt rõ ràng.

Cấu hình:

* ``GEMINI_API_KEY`` – biến môi trường, ưu tiên cao nhất;
* hoặc header ``X-Gemini-Key`` do người dùng nhập trên web (không lưu ở server).
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import urllib.error
import urllib.request
from typing import Iterable

from .schema import FORM_GROUPS
from .spec import DATA_KEYS, TITLES

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
TIMEOUT = int(os.environ.get("GEMINI_TIMEOUT", "180"))
MAX_EDGE = 2000          # px – đủ đọc chữ viết tay, ảnh gửi đi nhỏ
JPEG_QUALITY = 90
MAX_IMAGES = 24

# Model cũ đã bị khai tử → tự chuyển sang model mặc định
_RETIRED = re.compile(r"^gemini-(1\.|pro-vision|3\.5-flash|3\.7-)")

FORM_DEVICE = {
    "44": "Máy biến áp 1 pha (MBA 1P)",
    "45": "Máy cắt hạ thế (MCCB)",
    "46": "Chống sét van (LA)",
    "47": "Cầu chì tự rơi (FCO)",
    "48": "Điện trở nối đất",
}


class GeminiError(RuntimeError):
    """Lỗi khi gọi Gemini (đã dịch sang tiếng Việt cho người dùng cuối)."""


# --------------------------------------------------------------------------- #
# Ảnh
# --------------------------------------------------------------------------- #
def prepare_image(blob: bytes, max_edge: int = MAX_EDGE) -> tuple[str, str]:
    """Thu nhỏ ảnh và trả về ``(mime, base64)``.

    Không có Pillow thì gửi nguyên ảnh gốc – Gemini vẫn đọc được, chỉ tốn băng
    thông hơn.
    """
    try:
        from PIL import Image, ImageOps
    except Exception:                                   # pragma: no cover
        return _guess_mime(blob), base64.b64encode(blob).decode()

    try:
        img = Image.open(io.BytesIO(blob))
        img = ImageOps.exif_transpose(img)               # ảnh chụp dọc bằng điện thoại
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.thumbnail((max_edge, max_edge), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return "image/jpeg", base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return _guess_mime(blob), base64.b64encode(blob).decode()


def _guess_mime(blob: bytes) -> str:
    if blob[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #
def _field_lines(form: str) -> list[str]:
    """Sinh danh sách khoá + nhãn tiếng Việt của một mẫu (thẳng từ schema)."""
    out: list[str] = []
    for g in FORM_GROUPS[form]:
        if "table" in g:
            t = g["table"]
            cols = []
            for c in t["columns"]:
                col = f'"{c["key"]}" ({c["label"]}'
                if c.get("unit"):
                    col += f', {c["unit"]}'
                cols.append(col + ")")
            if t.get("stt"):
                cols.insert(0, '"stt" (số thứ tự)')
            out.append(f'  - "{t["key"]}": danh sách dòng, mỗi dòng là object gồm '
                       + ", ".join(cols))
            if t.get("kind") == "fixed":
                keys = ", ".join(f'"{r["key"]}" ({r["label"]})' for r in t["rows"])
                out.append(f"    + object này luôn có đúng 3 khoá: {keys}")
            continue
        for f in g.get("fields", []):
            unit = f' – đơn vị {f["unit"]}' if f.get("unit") else ""
            hint = f' – {f["hint"]}' if f.get("hint") else ""
            typ = {"code": "chỉ chữ số", "date": "dd/mm/yyyy",
                   "number": "số, dấu phẩy thập phân"}.get(f["type"], "")
            extra = f" [{typ}]" if typ else ""
            out.append(f'  - "{f["key"]}": {f["label"]}{unit}{extra}{hint}')
    return out


def build_prompt(forms: Iterable[str] | None = None) -> str:
    """Prompt tiếng Việt, liệt kê đúng khoá cần đọc cho từng mẫu."""
    forms = list(forms or sorted(FORM_GROUPS))
    parts: list[str] = []
    parts.append(
        "Bạn là chuyên viên nhập liệu của CÔNG TY CP THÍ NGHIỆM ĐIỆN TOÀN CẦU.\n"
        "Nhiệm vụ: đọc các ảnh biên bản kiểm định viết tay tại hiện trường (mỗi ảnh "
        "là một tờ biên bản, có thể có ảnh thiết bị/tem dán kèm) và trả về DUY NHẤT "
        "một khối JSON để phần mềm tự điền vào biểu mẫu Word.\n"
    )
    parts.append("=== QUY TẮC BẮT BUỘC ===\n"
                 "1. Chỉ đọc những gì NHÌN THẤY trên ảnh. Không suy đoán, không bịa số, "
                 "không tự tính toán thay người ghi (trừ khi ảnh đã ghi sẵn kết quả).\n"
                 "2. Không đọc chắc chắn được thì để chuỗi rỗng \"\" và ghi lý do vào "
                 "\"ai_notes\" của biên bản đó. Tuyệt đối không đoán bừa.\n"
                 "3. Giữ nguyên dấu tiếng Việt, chữ hoa/thường và đơn vị như trên ảnh "
                 "(kV, kVA, A, MΩ, µΩ, Ω, Hz, µA, kW, %). Không đổi đơn vị.\n"
                 "4. Số đo dùng DẤU PHẨY thập phân kiểu Việt Nam: 3,52 (không viết 3.52). "
                 "Giá trị vượt thang đo giữ nguyên dấu lớn hơn: >5000, >10000.\n"
                 "5. Ngày tháng xuất ra đúng dạng dd/mm/yyyy, đủ 2 chữ số ngày và tháng: "
                 "\"1/11/2026\" → \"01/11/2026\".\n"
                 "6. Số máy, số tem, số công tơ: chỉ ghi chữ số (bỏ dấu cách, gạch ngang, "
                 "ký tự lạ). Chữ O/o thành số 0, chữ l/I thành số 1 nếu rõ ràng là chữ số.\n"
                 "7. Một tờ biên bản có thể chụp thành nhiều ảnh (ảnh trên + ảnh dưới): "
                 "hãy GỘP lại thành một biên bản, không tạo 2 biên bản trùng.\n"
                 "8. Chỉ tạo những dòng bảng có thật trên ảnh. Không thêm dòng trống.\n"
                 "9. Trả về JSON thuần, không kèm lời giải thích, không dùng markdown.\n")

    parts.append("=== DANH SÁCH ẢNH ===\n"
                 "Mỗi ảnh được gửi kèm nhãn \"image_index = N\" ngay trước nó. "
                 "Dùng đúng số N đó khi trích dẫn nguồn.\n")

    parts.append("=== KHOÁ CHUNG (mọi biên bản) ===\n"
                 '"thong_tin_chung": {\n'
                 '  "ten_cong_trinh": tên công trình/trạm, ví dụ "Trạm biến áp 50kVA – DOANH NGHIỆP TƯ NHÂN E-GREEN",\n'
                 '  "dia_chi": địa chỉ đầy đủ (khu phố/xã/huyện/tỉnh),\n'
                 '  "don_vi_yêu_cầu": tên đơn vị yêu cầu kiểm định (viết đúng như ảnh),\n'
                 '  "ly_do_kiem_dinh": một trong "Sau sự cố", "Định kỳ", "Lắp đặt mới", "Hiện trường",\n'
                 '  "noi_kiem_dinh": "Tại hiện trường" hoặc "Tại phòng thí nghiệm",\n'
                 '  "ngay_kiem_dinh": dd/mm/yyyy,\n'
                 '  "ngay_lap_bien_ban": dd/mm/yyyy,\n'
                 '  "can_bo_ky_ten": {"nguoi_thu": …, "nguoi_kiem_tra": …, "p_giam_doc": …}\n'
                 "}\n")

    parts.append("=== CẤU TRÚC TRẢ VỀ ===\n"
                 "{\n"
                 '  "context_photos": [{"image_index": 0, "summary": "ảnh này chụp gì"}],\n'
                 '  "reports": [\n'
                 "    {\n"
                 '      "report_type": "44" | "45" | "46" | "47" | "48",\n'
                 '      "source_image_indices": [các image_index của tờ biên bản này],\n'
                 '      "confidence": "high" | "medium" | "low",\n'
                 '      "ai_notes": ["điểm chưa chắc chắn, chữ mờ, số bị sửa…"],\n'
                 '      "thong_tin_chung": {…như trên, chỉ các khoá đọc được…},\n'
                 '      "data": {…các khoá của mẫu tương ứng…}\n'
                 "    }\n"
                 "  ]\n"
                 "}\n"
                 'Nếu ảnh không phải biên bản nào trong 5 mẫu dưới đây thì cho vào '
                 '"context_photos" và KHÔNG tạo report.\n')

    for form in forms:
        parts.append(f"=== MẪU {form}: {TITLES[form]} – {FORM_DEVICE[form]} "
                     f"(khoá report_type = \"{form}\") ===\n"
                     "Các khoá của \"data\":\n" + "\n".join(_field_lines(form)) + "\n")
        key = DATA_KEYS[form]
        parts.append(f"(Khi phần mềm lưu, \"data\" của mẫu {form} nằm dưới khoá "
                     f"\"{key}\".)\n")

    parts.append(
        "=== VÍ DỤ MỘT DÒNG BẢNG ===\n"
        'Mẫu 45, dòng thứ nhất: {"stt": "1", "rcd_close": ">5000", "rcd_open": ">5000", '
        '"rtx_a": "273", "rtx_b": "275", "rtx_c": "279", "utest": "3", "dong_cat": "5", '
        '"ket_qua": "Đạt", "so_tem": "017215"}\n'
        "Nhãn \"Chỉ danh\" nếu ảnh không ghi thì BỎ TRỐNG (phần mềm tự ghép).\n"
        "Nhãn \"Kết luận\" chỉ chép khi ảnh có câu kết luận; không có thì bỏ trống.\n"
    )
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Gọi API
# --------------------------------------------------------------------------- #
def resolve_key(explicit: str | None = None) -> str:
    key = (explicit or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        raise GeminiError(
            "Chưa có API key Gemini. Đặt biến môi trường GEMINI_API_KEY khi chạy "
            "server, hoặc dán key vào ô “API key Gemini” trên giao diện."
        )
    return key


def _request(url: str, *, data: dict | None = None, method: str = "GET") -> dict:
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            payload = json.loads(exc.read().decode())
            detail = (payload.get("error") or {}).get("message") or ""
        except Exception:
            pass
        if exc.code in (400, 403):
            raise GeminiError(
                "API key không hợp lệ hoặc không có quyền dùng model này"
                + (f" ({detail})" if detail else "")
            ) from exc
        if exc.code == 429:
            raise GeminiError("Đã vượt hạn mức gọi Gemini (429). Thử lại sau ít phút.") from exc
        raise GeminiError(f"Gemini trả về lỗi {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise GeminiError(f"Không kết nối được tới Gemini: {exc.reason}") from exc
    except TimeoutError as exc:
        raise GeminiError("Gemini phản hồi quá lâu (timeout). Thử lại với ít ảnh hơn.") from exc


def list_models(key: str | None = None) -> list[str]:
    """Các model hỗ trợ ``generateContent`` – cho dropdown trên giao diện."""
    key = resolve_key(key)
    data = _request(f"{GEMINI_BASE}/models?key={key}&pageSize=200")
    out = []
    for m in data.get("models", []):
        name = (m.get("name") or "").removeprefix("models/")
        methods = m.get("supportedGenerationMethods") or []
        if "generateContent" in methods and name.startswith("gemini"):
            out.append(name)

    def rank(n: str):
        # ưu tiên flash mới → pro
        return ("3." in n, "2.5" in n, "flash" in n, "lite" not in n, n)

    return sorted(out, key=rank, reverse=True)


def _wire_model(model: str) -> str:
    model = (model or DEFAULT_MODEL).strip().removeprefix("models/")
    if _RETIRED.match(model):
        return "gemini-2.5-flash"
    return model


def parse_json_loose(text: str) -> dict:
    """Bóc JSON khỏi câu trả lời (kể cả khi bị bọc ```json … ```)."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
    raise GeminiError("Gemini trả về không phải JSON hợp lệ")


def call_gemini(
    images: list[bytes],
    *,
    key: str | None = None,
    model: str | None = None,
    forms: Iterable[str] | None = None,
) -> dict:
    """Gửi ảnh cho Gemini, trả về JSON thô (đã parse)."""
    if not images:
        raise GeminiError("Chưa có ảnh nào để nhận dạng")
    if len(images) > MAX_IMAGES:
        raise GeminiError(f"Chỉ gửi tối đa {MAX_IMAGES} ảnh một lần")
    key = resolve_key(key)
    model = _wire_model(model or DEFAULT_MODEL)
    prompt = build_prompt(forms)

    parts: list[dict] = [{"text": prompt}]
    for i, blob in enumerate(images):
        mime, b64 = prepare_image(blob)
        parts.append({"text": f"image_index = {i}"})
        parts.append({"inline_data": {"mime_type": mime, "data": b64}})

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "maxOutputTokens": 16384,
        },
    }
    url = f"{GEMINI_BASE}/models/{model}:generateContent?key={key}"
    data = _request(url, data=payload, method="POST")

    candidates = data.get("candidates") or []
    if not candidates:
        reason = (data.get("promptFeedback") or {}).get("blockReason")
        raise GeminiError(
            "Gemini không trả về kết quả" + (f" (bị chặn: {reason})" if reason else "")
        )
    texts = [
        p.get("text", "")
        for p in ((candidates[0].get("content") or {}).get("parts") or [])
        if isinstance(p, dict)
    ]
    raw = "".join(texts).strip()
    if not raw:
        finish = candidates[0].get("finishReason")
        raise GeminiError(
            "Gemini trả về nội dung rỗng" + (f" (finishReason: {finish})" if finish else "")
        )
    return parse_json_loose(raw)


# --------------------------------------------------------------------------- #
# Chuẩn hoá kết quả về đúng JSON của tool
# --------------------------------------------------------------------------- #
_SERIES_HINT = {
    "44": {"r_cuon_day_1_chieu_ohm.cao_ap": 5,
           "r_cuon_day_1_chieu_ohm.ha_ap_mOhm": 2,
           "ti_so_bien_ap.ha_1": 5, "ti_so_bien_ap.ha_2": 5},
}

_FIXED_ROWS = {
    "44": ("r_cach_dien_Mohm", ["cao_vo_ha1", "cao_vo_ha2", "ha1_ha2"]),
}


def _deep_set(target: dict, path: list[str], value) -> None:
    cur = target
    for p in path[:-1]:
        cur = cur.setdefault(p, {})
        if not isinstance(cur, dict):
            return
    cur[path[-1]] = value


def _to_list(value, n: int | None) -> list[str]:
    if isinstance(value, dict):
        value = list(value.values())
    if not isinstance(value, list):
        value = [value] if value not in (None, "") else []
    out = [str(v).strip() if v is not None else "" for v in value]
    if n:
        out = (out + [""] * n)[:n]
    return out


def _row_from_mapping(mapping: dict, columns: list[dict], *, stt: bool, index: int) -> dict:
    row: dict[str, str] = {}
    if stt:
        row["stt"] = str(mapping.get("stt") or index + 1)
    for col in columns:
        v = mapping.get(col["key"])
        row[col["key"]] = "" if v is None else str(v).strip()
    return row


def normalize_ai_result(raw: dict, *, forms: Iterable[str] | None = None) -> dict:
    """Đổi JSON của Gemini thành JSON chuẩn của tool.

    Kết quả: ``{"thong_tin_chung": {...}, "bien_ban_44_mba": {...}, ...,
    "_ai": {"notes": [...], "sources": {...}, "context": [...]}}``

    Hàm này chịu được cả JSON hơi lệch: ``data`` dạng phẳng hay lồng, bảng dạng
    list-of-object hay list-of-list, ``bien_ban_45_mccb: {rows: [...]}`` …
    """
    forms = list(forms or sorted(FORM_GROUPS))
    out: dict = {}
    notes: list[str] = []
    sources: dict[str, list[int]] = {}
    context: list[dict] = []

    common = raw.get("thong_tin_chung") or raw.get("common") or {}
    if isinstance(common, dict):
        tt = {k: v for k, v in common.items() if v not in (None, "")}
        if tt:
            out["thong_tin_chung"] = tt

    context = [c for c in (raw.get("context_photos") or []) if isinstance(c, dict)]

    reports = raw.get("reports")
    if not isinstance(reports, list):
        # dạng phẳng: {"bien_ban_44_mba": {...}, ...}
        reports = []
        for form in forms:
            key = DATA_KEYS[form]
            for k in (key, f"bien_ban_{form}", f"report_{form}", form):
                if isinstance(raw.get(k), dict):
                    reports.append({"report_type": form, "data": raw[k], "_key": k})
                    break

    for rep in reports:
        if not isinstance(rep, dict):
            continue
        form = str(rep.get("report_type") or rep.get("type") or rep.get("_key") or "").strip()
        form = form.replace("bien_ban_", "")[:2]
        if form not in FORM_GROUPS:
            continue
        block = rep.get("data")
        if not isinstance(block, dict):
            block = {k: v for k, v in rep.items()
                     if k not in ("report_type", "type", "source_image_indices",
                                  "ai_notes", "confidence", "thong_tin_chung", "common")}
        block = dict(block)
        block.pop("thong_tin_chung", None)

        # gộp thông tin chung của biên bản vào khoá chung
        rep_common = rep.get("thong_tin_chung") or rep.get("common")
        if isinstance(rep_common, dict) and rep_common:
            merged = dict(out.get("thong_tin_chung") or {})
            for k, v in rep_common.items():
                if v not in (None, "") and not merged.get(k):
                    merged[k] = v
            if merged:
                out["thong_tin_chung"] = merged

        # --- bảng ---------------------------------------------------------
        for title, table in _tables(form):
            src_key, src = _table_source(block, table)
            if src is None:
                continue
            if table.get("kind") == "fixed":
                rows = []
                for rk in table["rows"]:
                    rk = rk["key"] if isinstance(rk, dict) else rk
                    item = (src or {}).get(rk) if isinstance(src, dict) else None
                    rows.append(_row_from_mapping(item or {}, table["columns"],
                                                  stt=False, index=0) | {"key": rk})
                block[table["key"]] = {"rows": rows}
                continue
            if isinstance(src, dict):
                src = src.get("rows") or src.get("ket_qua_thu_nghiem") or list(src.values())
            if not isinstance(src, list):
                continue
            rows = []
            for i, item in enumerate(src):
                if isinstance(item, dict):
                    rows.append(_row_from_mapping(item, table["columns"],
                                                  stt=bool(table.get("stt")), index=i))
                elif isinstance(item, (list, tuple)):
                    if table.get("stt"):
                        rows.append(_row_from_mapping(
                            dict(zip([c["key"] for c in table["columns"]], item)),
                            table["columns"], stt=False, index=i) | {"stt": str(i + 1)})
                    else:
                        rows.append(_row_from_mapping(
                            dict(zip([c["key"] for c in table["columns"]], item)),
                            table["columns"], stt=False, index=i))
                elif isinstance(item, str):
                    cols = [c["key"] for c in table["columns"]]
                    vals = [v.strip() for v in item.split("|")]
                    rows.append(_row_from_mapping(dict(zip(cols, vals)), table["columns"],
                                                  stt=bool(table.get("stt")), index=i))
            if rows:
                block[table["key"]] = {"rows": rows}
                if src_key and src_key != table["key"]:
                    block.pop(src_key, None)

        # --- dãy số cố định ----------------------------------------------
        for path_s, n in _SERIES_HINT.get(form, {}).items():
            path = path_s.split(".")
            cur = block
            for p in path[:-1]:
                cur = cur.get(p) if isinstance(cur, dict) else None
                if cur is None:
                    break
            if isinstance(cur, dict) and path[-1] in cur:
                cur[path[-1]] = _to_list(cur[path[-1]], n)

        # --- dữ liệu kiểu cũ (ô phẳng) -> rows[] -------------------------
        if not _has_rows(block, form):
            legacy = _legacy_rows(form, block)
            if legacy:
                table = next(t for _, t in _tables(form) if t.get("kind") == "rows")
                block[table["key"]] = {"rows": legacy}

        # --- mẫu 48: 1 dòng phẳng -> rows[] ------------------------------
        if form == "48":
            if not block.get("rows") and any(block.get(k) for k in
                                             ("chi_danh", "gia_tri_do_Ohm", "gia_tri_do")):
                block["rows"] = {"rows": [{
                    "stt": "1",
                    "chi_danh": block.get("chi_danh") or "",
                    "ket_noi_trung_tinh": block.get("ket_noi_trung_tinh") or "",
                    "loai_tiep_dat": block.get("loai_tiep_dat") or "",
                    "gia_tri_do": block.get("gia_tri_do_Ohm") or block.get("gia_tri_do") or "",
                }]}

        for k in ("thiet_bi_do", "ket_luan", "chi_danh", "so_luong", "so_bien_ban",
                  "hieu", "loai", "kieu", "hieu_may", "so_tem", "so_may"):
            if isinstance(block.get(k), (int, float)):
                block[k] = str(block[k])

        notes.extend(str(n) for n in (rep.get("ai_notes") or []))
        idx = rep.get("source_image_indices") or []
        if idx:
            sources[form] = [int(i) for i in idx if isinstance(i, (int, float))]

        out[DATA_KEYS[form]] = block

    out["_ai"] = {"notes": notes, "sources": sources, "context": context}
    return out


def _tables(form: str):
    from .schema import tables_of
    return list(tables_of(form))


def _has_rows(block: dict, form: str) -> bool:
    for _, t in _tables(form):
        if t.get("kind") != "rows":
            continue
        val = block.get(t["key"])
        if isinstance(val, dict) and val.get("rows"):
            return True
        if isinstance(val, list) and val:
            return True
    return False


def _legacy_rows(form: str, block: dict) -> list[dict]:
    """Dữ liệu do con người nhập tay (ô phẳng) → một dòng bảng."""
    if form == "45":
        r = block.get("r_cach_dien_Mohm") or {}
        tx = block.get("r_tiep_xuc_uohm") or {}
        if not (r or tx):
            return []
        return [{
            "stt": "1",
            "rcd_close": r.get("close", ">5000"),
            "rcd_open": r.get("open", ">5000"),
            "rtx_a": tx.get("pha_a", ""), "rtx_b": tx.get("pha_b", ""),
            "rtx_c": tx.get("pha_c", ""),
            "utest": block.get("u_test_kV", "3"),
            "dong_cat": block.get("dong_cat_s", "5"),
            "ket_qua": block.get("ket_qua", "Đạt"),
            "so_tem": block.get("so_tem", ""),
        }]
    if form == "46":
        if not block.get("r_cach_dien_Mohm"):
            return []
        return [{"doi_tuong_do": block.get("chi_danh") or "LA 01",
                 "r_cach_dien": block.get("r_cach_dien_Mohm", ""),
                 "dong_ro": block.get("dong_ro_uA", ""),
                 "u_ac": block.get("u_ac_tang_cao_kV", "")}]
    if form == "47":
        r = block.get("r_cach_dien_Mohm") or {}
        u = block.get("u_ac_tang_cao_kV") or {}
        if not (r or u):
            return []
        return [{"thiet_bi": block.get("chi_danh") or "FCO 01",
                 "rcd_truoc": r.get("truoc_thu", ">10000"),
                 "rcd_sau": r.get("sau_thu", ">10000"),
                 "ac_kho": u.get("kho", "60"), "ac_uot": u.get("uot", "50"),
                 "dong_cat": block.get("dong_cat_s", "5"),
                 "ket_qua": block.get("ket_qua", "Đạt")}]
    return []


def _table_source(block: dict, table: dict):
    """Tìm dữ liệu bảng trong block, chấp nhận vài tên khoá quen thuộc."""
    for key in (table["key"], "ket_qua_thu_nghiem", f"{table['key']}_rows"):
        val = block.get(key)
        if isinstance(val, list) and val:
            return key, val
        if isinstance(val, dict) and val.get("rows"):
            return key, val
    return None, None
