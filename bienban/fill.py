"""Bộ điền form: JSON chuẩn → biên bản Word của công ty.

Điền từng mẫu trong 44..48. Mỗi mẫu được xử lý theo 3 lớp, theo đúng thứ tự
"từ trên xuống, từ trái sang phải" của file Word:

1. **Khung**: số biên bản + ngày lập (bảng tiêu đề), tiêu đề thiết bị.
2. **Ô nhãn**: mọi câu ``Nhãn: giá trị`` trong thân bài (kể cả 2–3 ô trên một
   dòng ngăn bằng tab) – xem :mod:`bienban.labels`.
3. **Bảng số liệu**: các bảng đo (cách điện, R một chiều, tỉ số biến áp,
   MCCB, LA, FCO, điện trở nối đất).

Mẫu 44 (.doc cũ) đã được dựng lại thành ``.docx`` chuẩn layout công ty bằng
``tools/build_template_44.py`` (giữ nguyên nội dung và thứ tự mục).
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Callable

import docx
from docx.oxml.ns import qn

from . import labels as L
from .normalize import (
    digits_only,
    flexible,
    norm_date,
    norm_number,
    norm_text,
    quantity_both,
)
from .ooxml import cell_text, para_text, set_cell_text, set_para_text
from .schema import FORM_GROUPS
from .watermark import apply_watermark
from .spec import (DATA_KEYS, DOC_KIND, LABELS, TABLE_HEADER_ROWS,
                   TABLE_PROBES, TEMPLATES, TITLES)

P = qn("w:p")
TBL = qn("w:tbl")
TR = qn("w:tr")
TC = qn("w:tc")

DEFAULT_CONFIG = {
    "company": {
        "name": "CÔNG TY CP THÍ NGHIỆM ĐIỆN TOÀN CẦU",
        "code_suffix": "/BB-TC",
    },
    "style": {
        # "template": giữ đúng định dạng mẫu; "bold_upper": in đậm + in hoa
        "header_values": "template",
        "bold_header_values": False,
        "upper_header_values": False,
        "bold_values": False,
        "upper_values": False,
    },
    "empty_placeholder": "-",
    "defaults": {
        "tan_so": "50Hz",
        "so_pha": "01",
        "loai": "MCCB",
        "nuoc_san_xuat": "Việt Nam",
        "kiem_tra_ben_ngoai": "Bình thường",
        "dos": "Kyoritsu 3125A; CA 6255; DTV-70/50",
        "tieu_chuan": "QCVN QTĐ-5,6,7: 2009/BCT",
        "thoi_gian_thu": "1 phút",
        "noi_kiem_dinh": "Tại hiện trường",
        "ly_do_kiem_dinh": "Sau sự cố",
    },
    "conclusions": {
        "default_template": "{qty} {device} trên đạt yêu cầu đóng điện vận hành",
    },
    # Chuỗi AI dự phòng: model chính -> model khác -> key dự phòng (đều của Gemini)
    "ai": {
        # Để trống = tự dò model mới nhất theo key, không bao giờ ghim model đã chết.
        "default_model": "",
        # Chỉ dùng khi model tự dò không chạy được; tool vẫn tự dò lại nếu Google khai tử.
        "fallback_models": ["gemini-3.6-flash", "gemini-3-flash-preview",
                            "gemini-2.5-flash"],
        "fallback_keys": [],          # có thể điền key thứ hai từ config.json
    },
}


# --------------------------------------------------------------------------- #
# Cấu hình
# --------------------------------------------------------------------------- #
def deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | Path | None = None) -> dict:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if path:
        import json

        with open(path, encoding="utf-8") as fh:
            cfg = deep_merge(cfg, json.load(fh))
    return cfg


# --------------------------------------------------------------------------- #
# Truy cập dữ liệu
# --------------------------------------------------------------------------- #
def get_value(values: dict, path: str):
    return L._get(values, path)


def _first(values: dict, *paths):
    for p in paths:
        v = get_value(values, p)
        if v not in (None, "", [], {}):
            return v
    return None


def derive_values(form: str, values: dict) -> dict:
    """Suy ra vài giá trị còn thiếu từ dữ liệu đã có (không bịa số đo).

    * ``chi_danh`` – mẫu 45/46/47 luôn có dòng "Chỉ danh"; nếu JSON không ghi
      thì ghép từ hiệu/loại + dòng định mức, ví dụ ``MCCB 250A``,
      ``LA 18kV-10kA``, ``FCO – 100A``.
    """
    if values.get("chi_danh"):
        return values
    if form == "45":
        loai = norm_text(values.get("loai") or "MCCB")
        dong = norm_text(values.get("dong_dinh_muc"))
        if dong:
            values["chi_danh"] = f"{loai} {dong}"
    elif form == "46":
        u = norm_text(values.get("dien_ap_dinh_muc"))
        i = norm_text(values.get("dong_xa_toi_da")).replace(" ", "")
        if u:
            values["chi_danh"] = f"LA {u}" + (f"-{i}" if i else "")
    elif form == "47":
        dong = norm_text(values.get("dong_dinh_muc"))
        if dong:
            values["chi_danh"] = f"FCO – {dong}"
    return values



# --------------------------------------------------------------------------- #
# Xoá số liệu "mồi" in sẵn trong mẫu Word
# --------------------------------------------------------------------------- #
#: Ô chứa số đo (có phần thập phân, hoặc dấu >, hoặc số nguyên dài).
#: KHÔNG khớp "1".."5" của cột Nấc/STT nên không phá cấu trúc bảng.
_M_MEASURE = re.compile(r"^(?:[><]\s*)?\d{1,6}(?:[.,]\d+)?$")


#: Nhận xét kết luận chép sẵn trong mẫu ("Đạt") — cũng phải dọn.
_M_VERDICT = re.compile(r"^(đạt|không đạt|pass|fail)$", re.I)


def _is_measure_text(txt: str) -> bool:
    """``True`` nếu ô đang chứa một *số đo* chép sẵn từ biên bản mẫu."""
    t = (txt or "").strip()
    if not t or len(t) > 12:
        return False
    if not _M_MEASURE.match(t):
        return False
    # số nguyên 1..2 chữ số = số thứ tự / số nấc → giữ
    if t.isdigit():
        return len(t) >= 3
    return True


def wipe_template_measures(doc, form: str) -> int:
    """Xoá các số đo in sẵn trong **thân bảng** của mẫu.

    Vì sao cần: các file mẫu được dựng từ biên bản thật (092, 44…) nên trong
    ô bảng vẫn còn số của lần đo cũ. Nếu lần này AI đọc hụt một ô, bản in sẽ
    lặng lẽ giữ **số cũ** — nguy hiểm hơn nhiều so với ô trống. Hàm này dọn
    sạch trước, rồi bộ điền mới ghi số thật vào.

    Chỉ đụng tới ô nằm **sau hàng tiêu đề** và có nội dung đúng là một số đo;
    ô nhãn (“Cao – Vỏ”), ô đơn vị (“R60″ (MΩ)”) và cột Nấc/STT giữ nguyên.
    """
    headers = _headers_for(form)
    removed = 0
    for probe_key in _table_keys_for(form):
        t = _find_table(doc, probe_key)
        if t is None:
            continue
        # Số đo có thể nằm ngay trong HÀNG TIÊU ĐỀ (ô gộp dọc "an: 0,885…"),
        # nên chỉ bỏ qua đúng ô tiêu đề, không bỏ qua cả hàng theo chỉ số.
        header_rows = headers.get(probe_key, 1)
        seen: set = set()
        for ri, row in enumerate(t.rows):
            for ci, cell in enumerate(row.cells):
                tc = cell._tc
                # ô gộp: nhiều `cell` trỏ về cùng một phần tử XML — so sánh
                # DANH TÍNH của phần tử (Python `id()` bị tái dùng sau khi GC).
                if tc in seen:
                    continue
                seen.add(tc)
                if _is_multi_measure(cell.text):
                    # ô gộp kiểu "an: 0,885\nbn: 0,887\ncn: 0,889": bỏ phần
                    # số, chỉ giữ nhãn để filler ghi lại đủ 3 dòng.
                    _strip_number_suffix(cell)
                    removed += 1
                    continue
                is_measure = _is_measure_text(cell.text) or bool(
                    _M_VERDICT.match(cell.text.strip()))
                if not is_measure and ci > 0:
                    # cột số liệu (bỏ cột Nấc/STT ở ci=0) → "50", "3", "5",
                    # ">5000" đều là số đo, kể cả khi nằm ở hàng tiêu đề gộp
                    is_measure = bool(re.fullmatch(r"[><]?\d{1,4}", cell.text.strip()))
                if not is_measure:
                    continue
                for extra in cell.paragraphs[1:]:
                    extra._element.getparent().remove(extra._element)
                if cell.paragraphs:
                    for run in list(cell.paragraphs[0].runs):
                        run._element.getparent().remove(run._element)
                removed += 1
    return removed


#: Ô gộp nhiều số: "an: 0,885\nbn: 0,887\ncn: 0,889"
_M_MULTI = re.compile(r"[A-Za-zà-ỹ]{1,4}\s*:\s*(?:[><]\s*)?\d")


def _is_multi_measure(txt: str) -> bool:
    """``True`` nếu ô gộp chứa từ 1 số đo trở lên dạng ``nhãn: số``."""
    return bool(_M_MULTI.search(txt or ""))


def _strip_number_suffix(cell) -> None:
    """Xoá phần số của ô gộp, giữ lại nhãn (``an:``, ``bn:``, ``cn:``)."""
    for p in cell.paragraphs:
        for run in p.runs:
            t = run.text
            if not _M_MULTI.search(t):
                continue
            # giữ mọi thứ TRƯỚC nhãn đầu tiên (VD "Cuộn dây hạ áp (mΩ)"),
            # bỏ toàn bộ phần "an: 0,885 / bn: 0,887 / cn: 0,889"
            m = _M_MULTI.search(t)
            run.text = t[:m.start()]


def _headers_for(form: str) -> dict[str, int]:
    from .spec import TABLE_HEADER_ROWS
    return TABLE_HEADER_ROWS


def _table_keys_for(form: str) -> list[str]:
    """Các bảng cần dọn dẹp cho mẫu này (theo ``LABELS``)."""
    return [item["table"] for item in LABELS[form] if item.get("table")]


# --------------------------------------------------------------------------- #
# Lớp 1: khung (số biên bản, ngày lập, tiêu đề)
# --------------------------------------------------------------------------- #
def fill_frame(doc, form: str, data: dict, cfg: dict, log) -> list[str]:
    warnings: list[str] = []
    block = data.get(DATA_KEYS[form]) or {}
    so = norm_text(block.get("so_bien_ban") or data.get("so_bien_ban") or "")
    ngay = norm_date(
        block.get("ngay_lap_bien_ban")
        or data.get("thong_tin_chung", {}).get("ngay_lap_bien_ban")
        or ""
    )
    company = cfg["company"]["name"]
    got_so = got_ngay = False

    for p in L.iter_body_paragraphs(doc):
        t = para_text(p)
        if not re.search(r"[A-Za-zÀ-ỹ]", t):
            continue
        if re.search(r"\bSỐ\s*:", t, re.I):
            new = re.sub(r"(SỐ\s*:\s*)(.*)$", lambda m: m.group(1) + so, t, count=1)
            set_para_text(p, new)
            got_so = True
        elif re.search(r"\bNGÀY\s*:", t, re.I):
            new = re.sub(r"(NGÀY\s*:\s*)(.*)$", lambda m: m.group(1) + ngay, t, count=1)
            set_para_text(p, new)
            got_ngay = True
        elif flexible(t) == flexible(company):
            set_para_text(p, company)

    if not _ensure_title(doc, TITLES[form]):
        warnings.append("Không thấy dòng tiêu đề thiết bị để kiểm tra")

    doc_kind = DOC_KIND[form]
    if doc_kind != "KIỂM ĐỊNH":
        # mẫu 48 dùng "BIÊN BẢN THỬ NGHIỆM"
        for p in L.iter_body_paragraphs(doc):
            if flexible(para_text(p)) == flexible("BIÊN BẢN KIỂM ĐỊNH"):
                set_para_text(p, "BIÊN BẢN THỬ NGHIỆM")

    if not (got_so and got_ngay):
        warnings.append("Không điền được đủ SỐ / NGÀY ở phần tiêu đề")
    log(f"    ✓ Số biên bản                    = {so}")
    log(f"    ✓ Ngày lập                      = {ngay}")
    return warnings


def _ensure_title(doc, expected: str) -> bool:
    for p in L.iter_body_paragraphs(doc):
        t = para_text(p).strip()
        if flexible(t) == flexible(expected):
            return True
    return False


# --------------------------------------------------------------------------- #
# Lớp 3: bảng số liệu
# --------------------------------------------------------------------------- #
def _find_table(doc, key: str):
    """Tìm bảng theo ``key`` trong :data:`TABLE_PROBES`."""
    probes, min_cols = TABLE_PROBES[key]
    want = [flexible(x) for x in probes]
    for t in doc.tables:
        if len(t.columns) < min_cols:
            continue
        hay = flexible(" ".join(cell_text(tc) for tc in t._tbl.iter(TC)))
        if all(w in hay for w in want):
            return t
    return None


def _rows(t):
    return t.rows


def _put(tc, text, bold=None):
    if text in (None, ""):
        return
    set_cell_text(tc, str(text), bold=bold)


def _put_force(tc, text, bold=None):
    """Ghi cả giá trị rỗng (dòng mới thêm vào phải sạch dữ liệu cũ)."""
    set_cell_text(tc, "" if text is None else str(text), bold=bold)


# --------------------------------------------------------------------------- #
# Dữ liệu dạng bảng mới (``{"rows": [...]}``) – dùng chung cho mọi bảng
# --------------------------------------------------------------------------- #
_NUMBER_TYPES = {"number", "code"}


BLANK_ROW_DOC = """
Quy ước dòng trống (theo yêu cầu của công ty)
--------------------------------------------
* Ô **để trống trong một dòng có số liệu khác** → in ``-`` (thói quen ghi
  biên bản giấy).
* Dòng **trống ở mọi ô** → bị xoá hẳn; dòng phía dưới dồn lên, số thứ tự đánh
  lại, và ``so_luong`` (nếu mẫu có ô này) tự giảm theo số dòng thật.
"""


def _is_blank(value) -> bool:
    if value is None:
        return True
    return str(value).strip() in ("", "-", "–", "—")


def compact_rows(rows: list[dict], table: dict) -> tuple[list[dict], int]:
    """Bỏ dòng trống hoàn toàn + đánh lại ``stt``. Trả về ``(dòng, số đã bỏ)``."""
    cols = [c["key"] for c in table.get("columns", [])]
    keep: list[dict] = []
    removed = 0
    for row in rows:
        if not isinstance(row, dict):
            removed += 1
            continue
        if cols and all(_is_blank(row.get(c)) for c in cols):
            removed += 1
            continue
        row = dict(row)
        if table.get("stt"):
            row["stt"] = str(len(keep) + 1)
        keep.append(row)
    return keep, removed


def apply_blank_rule(block: dict, table: dict) -> tuple[int, int]:
    """Chuẩn hoá 1 bảng trong ``block``: xoá dòng trống + cập nhật ``so_luong``."""
    key = table.get("key") or "rows"
    src = block.get(key)
    rows = src.get("rows") if isinstance(src, dict) else src
    if not isinstance(rows, list) or not rows:
        return 0, 0
    keep, removed = compact_rows(rows, table)
    flat = isinstance(src, list)
    if isinstance(src, dict):
        src["rows"] = keep
    else:
        block[key] = keep
    if flat:
        block["_rows_flat"] = True       # dữ liệu dạng list (JSON cũ): số lượng = số dòng
    if (table.get("sync_so_luong") or removed) and keep:
        block["so_luong"] = f"{len(keep):02d}"
    return len(keep), removed


def normalize_blank_rows(form: str, block: dict) -> tuple[dict, list[str]]:
    """Áp quy ước dòng trống cho mọi bảng của một mẫu (trả về bản sao + nhật ký)."""
    block = copy.deepcopy(block or {})
    log: list[str] = []
    for g in FORM_GROUPS.get(form, []):
        table = g.get("table")
        if not table or table.get("kind") == "fixed":
            continue
        rows = block.get(table.get("key") or "rows")
        rows = rows.get("rows") if isinstance(rows, dict) else rows
        if not isinstance(rows, list) or not rows:
            continue
        before = len(rows)
        kept, removed = apply_blank_rule(block, table)
        if removed:
            log.append(f"Bỏ {removed} dòng trống ở “{g.get('title', '')}” "
                       f"({before} → {kept} dòng)")
    return block, log


def table_spec(form: str, key: str) -> dict | None:
    """Định nghĩa bảng theo khoá dữ liệu (``rows``, ``r_cach_dien_Mohm``…)."""
    tables = [g["table"] for g in FORM_GROUPS.get(form, []) if g.get("table")]
    for t in tables:
        if t["key"] == key:
            return t
    # khoá tra theo bảng Word (``la``, ``mccb``…) nhưng dữ liệu nằm ở ``rows``
    row_tables = [t for t in tables if t.get("kind") == "rows"]
    if len(row_tables) == 1:
        return row_tables[0]
    return None


def _cell_value(col: dict, raw, blank: str = "") -> str:
    """Giá trị 1 ô; ``blank`` là thứ in ra khi ô trống (công ty dùng ``-``)."""
    if raw in (None, ""):
        return blank
    if col.get("type") in _NUMBER_TYPES:
        return norm_number(raw) if col.get("type") == "number" else digits_only(raw)
    return norm_text(raw)


def _clean_row(table: dict, row: dict, index: int, blank: str = "-") -> list[str]:
    """Đổi 1 dòng (object) thành list giá trị đúng thứ tự cột của bảng Word."""
    vals: list[str] = []
    for col in table["columns"]:
        vals.append(_cell_value(col, row.get(col["key"]), blank))
    if table.get("stt"):
        stt = digits_only(row.get("stt")) or str(index + 1)
        vals.insert(0, stt)
    return vals


def _fixed_row(table: dict, row: dict) -> list[str]:
    return [_cell_value(c, row.get(c["key"])) for c in table["columns"]]


def _rows_of(block: dict, key: str) -> list[dict] | None:
    """Đọc ``{"rows": [...]}``; chấp nhận cả ``{".....rows": [...]}``."""
    src = block.get(key)
    if src is None:
        src = block.get(f"{key}_rows")
    if isinstance(src, dict):
        for k in ("rows", f"{key}_rows", "ket_qua_thu_nghiem"):
            if isinstance(src.get(k), list):
                src = src[k]
                break
        else:
            if key == "rows":
                src = None
    if isinstance(src, list) and all(isinstance(x, dict) for x in src):
        return src
    return None


def fill_insulation(doc, block: dict, cfg, log) -> list[str]:
    blank = cfg.get("empty_placeholder", "-")
    t = _find_table(doc, "insulation")
    if t is None:
        return ["Không tìm thấy bảng 'Điện trở cách điện' (mục 2)"]
    data = block.get("r_cach_dien_Mohm") or {}
    rows_data = _rows_of(block, "r_cach_dien_Mohm")
    if rows_data:
        spec = table_spec("44", "r_cach_dien_Mohm") or {"columns": []}
        for ri, row in enumerate(rows_data[:3], start=1):
            if ri >= len(t.rows):
                break
            cells = t.rows[ri].cells
            for ci, col in enumerate(spec["columns"], start=1):
                if ci < len(cells):
                    _put_force(cells[ci]._tc, _cell_value(col, row.get(col["key"]), blank))
            log("    ✓ R cách điện {:<18}= {} | {} | {}".format(
                row.get("key") or f"dòng {ri}",
                _cell_value(spec["columns"][0], row.get(spec["columns"][0]["key"]), blank),
                _cell_value(spec["columns"][1], row.get(spec["columns"][1]["key"]), blank),
                _cell_value(spec["columns"][2], row.get(spec["columns"][2]["key"]), blank),
            ))
        return []
    names = {"cao_vo_ha1": "(Cao+Vỏ) - Hạ 1", "cao_vo_ha2": "(Cao+Vỏ) - Hạ 2",
             "ha1_ha2": "Hạ 1 - Hạ 2"}
    keys = list(names)
    for ri, key in enumerate(keys, start=1):
        if ri >= len(t.rows):
            break
        item = data.get(key) or {}
        cells = t.rows[ri].cells
        for ci, field in enumerate(("r60", "r15", "knt"), start=1):
            if ci < len(cells) and item.get(field) not in (None, ""):
                _put(cells[ci]._tc, norm_number(item[field]))
        log("    ✓ R cách điện {:<18}= {} | {} | {}".format(
            names[key],
            norm_number(item.get("r60")),
            norm_number(item.get("r15")),
            norm_number(item.get("knt")),
        ))
    return []


def fill_r_dc(doc, block: dict, cfg, log) -> list[str]:
    t = _find_table(doc, "r_dc")
    if t is None:
        return ["Không tìm thấy bảng 'Điện trở một chiều cuộn dây' (mục 3)"]
    data = block.get("r_cuon_day_1_chieu_ohm") or {}
    ca = data.get("cao_ap") or []
    ha = data.get("ha_ap_mOhm") or []
    row = t.rows[-1]
    cells = row.cells
    for i, v in enumerate(ca[:5]):
        if i + 1 < len(cells):
            _put(cells[i + 1]._tc, norm_number(v))
    for i, v in enumerate(ha[:2]):
        if 6 + i < len(cells):
            _put(cells[6 + i]._tc, norm_number(v))
    log("    ✓ R một chiều CA (Ω)           = " + ", ".join(norm_number(x) for x in ca))
    log("    ✓ R một chiều HA (mΩ)          = " + ", ".join(norm_number(x) for x in ha))
    return []


def fill_ratio(doc, block: dict, cfg, log) -> list[str]:
    t = _find_table(doc, "ratio")
    if t is None:
        return ["Không tìm thấy bảng 'Tỉ số biến áp' (mục 4)"]
    data = block.get("ti_so_bien_ap") or {}
    row = t.rows[-1]
    cells = [c._tc for c in row.cells]
    for i, v in enumerate((data.get("ha_1") or [])[:5]):
        if 1 + i < len(cells):
            _put(cells[1 + i], norm_number(v))
    for i, v in enumerate((data.get("ha_2") or [])[:5]):
        if 6 + i < len(cells):
            _put(cells[6 + i], norm_number(v))
    log("    ✓ Tỉ số biến áp – Hạ 1          = " + ", ".join(norm_number(x) for x in data.get("ha_1") or []))
    log("    ✓ Tỉ số biến áp – Hạ 2          = " + ", ".join(norm_number(x) for x in data.get("ha_2") or []))
    return []


def _fill_row_table(doc, key, rows_data: list[list[str]], log, name: str):
    t = _find_table(doc, key)
    if t is None:
        return [f"Không tìm thấy bảng '{name}'"]
    header_rows = TABLE_HEADER_ROWS[key]
    for i, vals in enumerate(rows_data):
        ri = header_rows + i
        if ri >= len(t.rows):
            break
        cells = t.rows[ri].cells
        for ci, v in enumerate(vals):
            if ci < len(cells):
                _put(cells[ci]._tc, v)
    log(f"    ✓ {name:<33}= {len(rows_data)} dòng số liệu")
    return []


def _resize_table(table, total_needed: int) -> None:
    """Cắt / nhân bản dòng cuối để bảng có đúng số dòng cần dùng."""
    while len(table.rows) > total_needed:
        tr = table.rows[-1]._tr
        tr.getparent().remove(tr)
    while len(table.rows) < total_needed:
        tr = copy.deepcopy(table.rows[-1]._tr)
        table.rows[-1]._tr.addnext(tr)


def fill_row_table(doc, form: str, key: str, block: dict, rows_data: list[dict],
                   name: str, log, data_key: str | None = None,
                   blank: str = "-") -> list[str]:
    """Điền bảng từ dữ liệu ``{"rows": [...]}`` – tự thêm/bớt dòng theo dữ liệu.

    ``key`` là khoá nhận diện bảng trong file Word (``la``, ``mccb``…);
    ``data_key`` là khoá trong JSON (mặc định ``rows``); ``blank`` là ký tự in
    vào ô trống (quy ước công ty: ``-``).
    """
    t = _find_table(doc, key)
    if t is None:
        return [f"Không tìm thấy bảng '{name}'"]
    spec = table_spec(form, data_key or "rows") or {"columns": []}
    header_rows = TABLE_HEADER_ROWS[key]
    _resize_table(t, header_rows + len(rows_data))
    stt_col = bool(spec.get("stt"))
    for i, row in enumerate(rows_data):
        cells = t.rows[header_rows + i].cells
        start = 0
        if stt_col and len(cells) > 1:
            _put(cells[0]._tc, digits_only(row.get("stt")) or str(i + 1), bold=True)
            start = 1
        for ci, col in enumerate(spec.get("columns", [])):
            if start + ci < len(cells):
                _put_force(cells[start + ci]._tc,
                           _cell_value(col, row.get(col["key"]), blank))
    log(f"    ✓ {name:<33}= {len(rows_data)} dòng số liệu")
    return []


def fill_mccb(doc, block: dict, cfg, log) -> list[str]:
    rows_data = _rows_of(block, "rows")
    if rows_data:
        return fill_row_table(doc, "45", "mccb", block, rows_data,
                              "Bảng kết quả thử nghiệm", log,
                              blank=cfg.get("empty_placeholder", "-"))
    rows = block.get("ket_qua_thu_nghiem")
    if not rows:
        r = block.get("r_cach_dien_Mohm") or {}
        tx = block.get("r_tiep_xuc_uohm") or {}
        rows = [[
            # KHÔNG mặc định ">5000": đó là số bịa. Không đọc được thì để trống,
            # người dùng in ra điền tay (đúng nguyên tắc "ô trống chỉ là cảnh báo").
            norm_number(r.get("close") or cfg.get("defaults", {}).get("r_close", "")),
            norm_number(r.get("open") or cfg.get("defaults", {}).get("r_open", "")),
            norm_number(tx.get("pha_a")),
            norm_number(tx.get("pha_b")),
            norm_number(tx.get("pha_c")),
            norm_number(block.get("u_test_kV")),
            norm_number(block.get("dong_cat_s")),
            norm_text(block.get("ket_qua") or ""),
            digits_only(block.get("so_tem")),
        ]]
    table = _find_table(doc, "mccb")
    if table is None:
        return ["Không tìm thấy bảng kết quả thử nghiệm MCCB"]
    _resize_table(table, TABLE_HEADER_ROWS["mccb"] + len(rows))
    for i, vals in enumerate(rows):
        cells = table.rows[TABLE_HEADER_ROWS["mccb"] + i].cells
        _put(cells[0]._tc, str(i + 1), bold=True)
        for ci, v in enumerate(vals, start=1):
            if ci < len(cells):
                _put(cells[ci]._tc, v)
    log(f"    ✓ Bảng kết quả thử nghiệm       = {len(rows)} dòng")
    return []


def fill_la(doc, block: dict, cfg, log) -> list[str]:
    rows_data = _rows_of(block, "rows")
    if rows_data:
        return fill_row_table(doc, "46", "la", block, rows_data,
                              "Bảng kết quả kiểm định LA", log,
                              blank=cfg.get("empty_placeholder", "-"))
    rows = block.get("ket_qua_thu_nghiem")
    if not rows:
        rows = [[
            norm_number(block.get("r_cach_dien_Mohm")),
            norm_number(block.get("dong_ro_uA")),
            norm_number(block.get("u_ac_tang_cao_kV")),
        ]]
    return _fill_row_table(doc, "la", rows, log, "Bảng kết quả kiểm định LA")


def fill_fco(doc, block: dict, cfg, log) -> list[str]:
    rows_data = _rows_of(block, "rows")
    if rows_data:
        return fill_row_table(doc, "47", "fco", block, rows_data,
                              "Bảng kết quả kiểm định FCO", log,
                              blank=cfg.get("empty_placeholder", "-"))
    rows = block.get("ket_qua_thu_nghiem")
    if not rows:
        r = block.get("r_cach_dien_Mohm") or {}
        u = block.get("u_ac_tang_cao_kV") or {}
        rows = [[
            norm_number(r.get("truoc_thu")),
            norm_number(r.get("sau_thu")),
            norm_number(u.get("kho")),
            norm_number(u.get("uot")),
            norm_number(block.get("dong_cat_s")),
            norm_text(block.get("ket_qua") or ""),
        ]]
    return _fill_row_table(doc, "fco", rows, log, "Bảng kết quả kiểm định FCO")


def fill_earth(doc, block: dict, cfg, log) -> list[str]:
    blank = cfg.get("empty_placeholder", "-")
    t = _find_table(doc, "earth")
    if t is None:
        return ["Không tìm thấy bảng kết quả đo điện trở nối đất"]
    rows_data = _rows_of(block, "rows")
    if rows_data:
        spec = table_spec("48", "rows") or {"columns": []}
        _resize_table(t, 1 + len(rows_data))
        for i, row in enumerate(rows_data):
            cells = t.rows[1 + i].cells
            _put(cells[0]._tc, digits_only(row.get("stt")) or str(i + 1), bold=True)
            for ci, col in enumerate(spec["columns"]):
                if 1 + ci < len(cells):
                    _put_force(cells[1 + ci]._tc, _cell_value(col, row.get(col["key"])))
        log(f"    ✓ Điện trở nối đất              = {len(rows_data)} dòng")
        return []
    cells = t.rows[1].cells
    _put(cells[0]._tc, "1", bold=True)
    _put(cells[1]._tc, norm_text(block.get("chi_danh")))
    _put(cells[2]._tc, norm_text(block.get("ket_noi_trung_tinh")))
    _put(cells[3]._tc, norm_text(block.get("loai_tiep_dat")))
    _put(cells[4]._tc, norm_number(block.get("gia_tri_do_Ohm")))
    log("    ✓ Điện trở nối đất              = {} Ω".format(norm_number(block.get("gia_tri_do_Ohm"))))
    # xoá các dòng trống còn lại (mẫu in sẵn STT 2..10)
    while len(t.rows) > 2:
        tr = t.rows[-1]._tr
        tr.getparent().remove(tr)
    return []


def fill_no_load(doc, block: dict, cfg, log) -> list[str]:
    t = _find_table(doc, "no_load")
    if t is None:
        return ["Không tìm thấy bảng 'Thí nghiệm không tải' (mục 5)"]
    d = block.get("khong_tai") or {}
    vals = [d.get("u0_V"), d.get("i0_A"), d.get("i0_pct"), d.get("p0_W")]
    row = t.rows[-1].cells
    for i, v in enumerate(vals):
        if i + 1 < len(row):
            _put(row[i + 1]._tc, norm_number(v))
    log("    ✓ Không tải                    U0={} V, I0={} A, I0%={}, P0={} W".format(
        *[norm_number(v) for v in vals]))
    return []


def fill_short_circuit(doc, block: dict, cfg, log) -> list[str]:
    t = _find_table(doc, "short_circuit")
    if t is None:
        return ["Không tìm thấy bảng 'Thí nghiệm ngắn mạch' (mục 6)"]
    d = block.get("ngan_mach") or {}
    vals = [d.get("uk_V"), d.get("uk_pct"), d.get("ik_A"), d.get("pk_W")]
    row = t.rows[-1].cells
    for i, v in enumerate(vals):
        if i + 1 < len(row):
            _put(row[i + 1]._tc, norm_number(v))
    log("    ✓ Ngắn mạch                    UN={} V, UN%={}, IN={} A, PN75={} W".format(
        *[norm_number(v) for v in vals]))
    return []


def fill_voltage_test(doc, block: dict, cfg, log) -> list[str]:
    t = _find_table(doc, "voltage_test")
    if t is None:
        return ["Không tìm thấy bảng 'Thử điện áp tăng cao' (mục 7)"]
    d = block.get("thu_dien_ap_tang_cao") or {}
    thoi_gian = norm_text(d.get("thoi_gian") or cfg["defaults"].get("thoi_gian_thu", "1 phút"))
    for ri, key in ((1, "cao_ap"), (2, "ha_ap")):
        if ri >= len(t.rows):
            break
        cells = t.rows[ri].cells
        if len(cells) > 1 and d.get(key) not in (None, ""):
            _put(cells[1]._tc, norm_number(d[key]))
        if len(cells) > 2:
            _put(cells[2]._tc, thoi_gian)
    log("    ✓ Thử điện áp tăng cao          CA={} kV, HA={} kV ({})".format(
        norm_number(d.get("cao_ap")), norm_number(d.get("ha_ap")), thoi_gian))
    return []



# --------------------------------------------------------------------------- #
# Mẫu 49 – MÁY BIẾN ÁP 3 PHA
# --------------------------------------------------------------------------- #
#: 3 dòng cố định của bảng điện trở cách điện MBA 3 pha
ROWS_3P_INSULATION = ("cao_vo", "cao_ha", "ha_vo")
#: 3 pha của cuộn dây cao áp (mẫu in 3 cột AB / BC / CA)
PHASES_3P = ("ab", "bc", "ca")


def fill_insulation_3p(doc, block: dict, cfg, log) -> list[str]:
    """Bảng 2 của mẫu 49: Cao – Vỏ / Cao – Hạ / Hạ – Vỏ (MBA 3 pha)."""
    blank = cfg.get("empty_placeholder", "-")
    t = _find_table(doc, "insulation_3p")
    if t is None:
        return ["Không tìm thấy bảng 'Điện trở cách điện' của MBA 3 pha (mục 2)"]
    data = block.get("r_cach_dien_Mohm") or {}
    rows_data = _rows_of(block, "r_cach_dien_Mohm")
    if rows_data:
        spec = table_spec("49", "r_cach_dien_Mohm") or {"columns": []}
        for ri, row in enumerate(rows_data[:3], start=1):
            if ri >= len(t.rows):
                break
            cells = t.rows[ri].cells
            for ci, col in enumerate(spec["columns"], start=1):
                if ci < len(cells):
                    _put_force(cells[ci]._tc,
                               _cell_value(col, row.get(col["key"]), blank))
            log("    ✓ R cách điện {:<10}= {} | {} | {}".format(
                row.get("key") or f"dòng {ri}",
                norm_number(row.get("r60")), norm_number(row.get("r15")),
                norm_number(row.get("knt"))))
        return []
    for ri, key in enumerate(ROWS_3P_INSULATION, start=1):
        if ri >= len(t.rows):
            break
        item = data.get(key) or {}
        cells = t.rows[ri].cells
        for ci, field in enumerate(("r60", "r15", "knt"), start=1):
            if ci < len(cells):
                _put(cells[ci]._tc, norm_number(item.get(field)))
        log("    ✓ R cách điện {:<10}= {} | {} | {}".format(
            key, norm_number(item.get("r60")), norm_number(item.get("r15")),
            norm_number(item.get("knt"))))
    return []


def fill_r_dc_3p(doc, block: dict, cfg, log) -> list[str]:
    """Bảng 3 của mẫu 49: cuộn cao áp AB/BC/CA × 5 nấc + hạ áp an/bn/cn.

    Bản in gộp 3 giá trị hạ áp vào **một ô** (``an: … bn: … cn: …``), khác mẫu
    44 có 2 cột HA 1 / HA 2.
    """
    t = _find_table(doc, "r_dc_3p")
    if t is None:
        return ["Không tìm thấy bảng 'Điện trở một chiều cuộn dây' của MBA 3 pha (mục 3)"]
    data = block.get("r_cuon_day_1_chieu_ohm") or {}
    phases = data.get("cao_ap") or {}
    if not isinstance(phases, dict):
        phases = {}
    # chấp nhận cả dạng phẳng: {"cao_ap": [...]} của mẫu 44
    flat = data.get("cao_ap") if isinstance(data.get("cao_ap"), list) else None
    for pi, phase in enumerate(PHASES_3P):
        vals = phases.get(phase) or (flat if pi == 0 and flat else []) or []
        for si, v in enumerate(list(vals)[:5]):
            ri = (1 if len(t.rows) > 6 else 0) + si + 1
            if ri >= len(t.rows):
                break
            cells = t.rows[ri].cells
            if 1 + pi < len(cells) and v not in (None, ""):
                _put(cells[1 + pi]._tc, norm_number(v))
    ha = data.get("ha_ap_mOhm") or {}
    if isinstance(ha, dict) and ha:
        text = "\n".join(f"{k}: {norm_number(ha.get(k))}"
                         for k in ("an", "bn", "cn") if ha.get(k) not in (None, ""))
        if text:
            target = t.rows[-1].cells
            _put(target[-1]._tc, text)
            log(f"    ✓ R một chiều hạ áp (mΩ)       = {text.replace(chr(10), ' | ')}")
    for phase in PHASES_3P:
        vals = phases.get(phase) or []
        if vals:
            log(f"    ✓ R một chiều CA pha {phase.upper():<8}= "
                + ", ".join(norm_number(x) for x in vals[:5]))
    return []


def fill_ratio_3p(doc, block: dict, cfg, log) -> list[str]:
    """Bảng 4 của mẫu 49: tỉ số K1 / K2 / K3 × 5 nấc."""
    t = _find_table(doc, "ratio_3p")
    if t is None:
        return ["Không tìm thấy bảng 'Tỉ số biến áp' của MBA 3 pha (mục 4)"]
    data = block.get("ti_so_bien_ap") or {}
    for ki, key in enumerate(("k1", "k2", "k3")):
        vals = data.get(key) or []
        if not vals and ki == 0:
            # dữ liệu cũ dùng ha_1 cho cột K1
            vals = data.get("ha_1") or []
        for si, v in enumerate(list(vals)[:5]):
            ri = si + 1
            if ri >= len(t.rows):
                break
            cells = t.rows[ri].cells
            if 1 + ki < len(cells) and v not in (None, ""):
                _put(cells[1 + ki]._tc, norm_number(v))
        if vals:
            log(f"    ✓ Tỉ số biến áp K{ki + 1:<10}= "
                + ", ".join(norm_number(x) for x in list(vals)[:5]))
    return []


def fill_voltage_test_3p(doc, block: dict, cfg, log) -> list[str]:
    """Bảng 7 của mẫu 49: Cao–(Hạ+vỏ) / Hạ–(Cao+vỏ)."""
    t = _find_table(doc, "voltage_test_3p")
    if t is None:
        return ["Không tìm thấy bảng 'Thử điện áp tăng cao' của MBA 3 pha (mục 7)"]
    d = block.get("thu_dien_ap_tang_cao") or {}
    thoi_gian = norm_text(d.get("thoi_gian")
                          or cfg["defaults"].get("thoi_gian_thu", "1 phút"))
    # 3 pha ưu tiên khoá riêng; nếu ảnh chỉ ghi "cao áp"/"hạ áp" thì vẫn dùng
    for ri, keys in ((1, ("cao_vo", "cao_ap")), (2, ("ha_vo", "ha_ap"))):
        if ri >= len(t.rows):
            break
        val = next((d.get(k) for k in keys if d.get(k) not in (None, "")), None)
        cells = t.rows[ri].cells
        if val is not None and len(cells) > 1:
            _put(cells[1]._tc, norm_number(val))
        if len(cells) > 2:
            _put(cells[2]._tc, thoi_gian)
    log("    ✓ Thử điện áp tăng cao          Cao–(Hạ+vỏ)={} kV, Hạ–(Cao+vỏ)={} kV ({})"
        .format(norm_number(d.get("cao_vo") or d.get("cao_ap")),
                norm_number(d.get("ha_vo") or d.get("ha_ap")), thoi_gian))
    return []

def fill_cap_ngam(doc, block: dict, cfg, log) -> list[str]:
    """Bảng 1 của mẫu 97: điện trở cách điện **theo pha** (Pha 1/2/3)."""
    t = _find_table(doc, "cap_ngam")
    if t is None:
        return ["Không tìm thấy bảng 'Điện trở cách điện' của cáp ngầm"]
    rows = _rows_of(block, "r_cach_dien_Mohm") or []
    for i, item in enumerate(rows[:3]):
        if i + 1 >= len(t.rows):
            break
        cells = t.rows[i + 1].cells
        _put(cells[1]._tc, norm_number(item.get("tieu_chuan")))
        _put(cells[2]._tc, norm_number(item.get("so_lieu_do")))
    if rows:
        log(f"    ✓ R cách điện cáp             = {len(rows[:3])} pha")
    return []


def fill_cap_ngam_dc(doc, block: dict, cfg, log) -> list[str]:
    """Bảng 2 của mẫu 97: điện áp một chiều tăng cao theo pha."""
    t = _find_table(doc, "cap_ngam_dc")
    if t is None:
        return ["Không tìm thấy bảng 'Điện áp một chiều tăng cao' của cáp ngầm"]
    rows = _rows_of(block, "thu_dien_ap_mot_chieu") or []
    for i, item in enumerate(rows[:3]):
        if i + 1 >= len(t.rows):
            break
        cells = t.rows[i + 1].cells
        _put(cells[1]._tc, norm_number(item.get("thoi_gian")))
        _put(cells[2]._tc, norm_number(item.get("dien_ap")))
        _put(cells[3]._tc, norm_number(item.get("dong_ro")))
    if rows:
        log(f"    ✓ Thử áp 1 chiều cáp          = {len(rows[:3])} pha")
    return []


TABLE_FILLERS: dict[str, Callable] = {
    "insulation": fill_insulation,
    "r_dc": fill_r_dc,
    "ratio": fill_ratio,
    "mccb": fill_mccb,
    "la": fill_la,
    "fco": fill_fco,
    "earth": fill_earth,
    "no_load": fill_no_load,
    "short_circuit": fill_short_circuit,
    "voltage_test": fill_voltage_test,
    "insulation_3p": fill_insulation_3p,
    "r_dc_3p": fill_r_dc_3p,
    "ratio_3p": fill_ratio_3p,
    "voltage_test_3p": fill_voltage_test_3p,
    "cap_ngam": fill_cap_ngam,
    "cap_ngam_dc": fill_cap_ngam_dc,
}


# --------------------------------------------------------------------------- #
# Kết luận
# --------------------------------------------------------------------------- #
def build_conclusion(form: str, block: dict, data: dict, cfg: dict) -> str:
    explicit = block.get("ket_luan") or block.get("kết_luận")
    if explicit:
        return norm_text(explicit)
    qty = block.get("so_luong") or 1
    rows = _rows_of(block, "rows")
    if block.get("_rows_flat") and rows is not None:
        qty = len(rows)                 # dữ liệu dạng list: số dòng chính là số lượng
    qty_text = quantity_both(qty)
    device = (block.get("ten_thiet_bi") or "").strip()
    if not device:
        device = {
            "44": "máy biến áp 1 pha",
            "45": "máy cắt hạ thế (MCCB)",
            "46": "chống sét van",
            "47": "FCO",
            "48": "điện trở nối đất",
            "49": "máy biến áp 3 pha",
            "93": "máy cắt hạ thế (ACB)",
            "97": "đoạn cáp ngầm trung thế",
        }[form]
    template = (cfg.get("conclusions") or {}).get("default_template") or \
        "{qty} {device} trên đạt yêu cầu đóng điện vận hành"
    text = template.format(qty=qty_text, device=device)
    return text[:1].upper() + text[1:]


# --------------------------------------------------------------------------- #
# API chính
# --------------------------------------------------------------------------- #
def render_form(
    form: str,
    data: dict,
    *,
    templates_dir: Path | str,
    out_dir: Path | str,
    cfg: dict | None = None,
    log: Callable[[str], None] = lambda s: None,
    suffix: str = "",
) -> tuple[Path, list[str]]:
    """Sinh 1 biên bản. Trả về ``(đường dẫn file, danh sách cảnh báo)``."""
    cfg = cfg or load_config()
    templates_dir = Path(templates_dir)
    out_dir = Path(out_dir)
    allowed = cfg.get("forms")
    if allowed and form not in allowed:
        raise ValueError(f"Mẫu {form} không nằm trong danh sách cho phép")

    tpl = templates_dir / TEMPLATES[form]
    if not tpl.exists():
        raise FileNotFoundError(f"Thiếu file mẫu: {tpl}")

    key = DATA_KEYS[form]
    block = data.get(key)
    if block is None:
        block = {}
        log(f"    ! Không có khoá {key} trong JSON – chỉ điền thông tin chung")

    doc = docx.Document(str(tpl))
    warnings: list[str] = []

    # Dọn số đo in sẵn trong mẫu TRƯỚC khi điền: ô nào không đọc được sẽ để
    # trống (in dấu "-") thay vì lặng lẽ giữ số của biên bản cũ.
    wiped = wipe_template_measures(doc, form)
    if wiped:
        log(f"    ✓ Dọn {wiped} ô số liệu cũ in sẵn trong mẫu")

    # số biên bản: ưu tiên block, sau đó data
    merged = dict(data)
    merged[key] = block
    warnings += fill_frame(doc, form, merged, cfg, log)

    # quy ước dòng trống: bỏ dòng trống hoàn toàn + tự giảm `so_luong`
    block, blank_log = normalize_blank_rows(form, block)
    merged[key] = block
    for line in blank_log:
        warnings.append(line)
        log(f"    ✓ {line}")

    # giá trị mặc định + kết luận suy ra
    values = copy.deepcopy(block)
    tt = copy.deepcopy(merged.get("thong_tin_chung") or {})
    for k, v in (cfg.get("defaults") or {}).items():
        values.setdefault(k, v)
    if not values.get("tan_so"):
        values["tan_so"] = cfg["defaults"].get("tan_so", "50Hz")
    values["thong_tin_chung"] = tt
    values = derive_values(form, values)
    if form != "48":
        values["ket_luan"] = build_conclusion(form, block, merged, cfg)

    warnings += L.fill_labels(doc, LABELS[form], values, cfg, log)

    for key in ("insulation", "r_dc", "ratio", "no_load", "short_circuit",
                "voltage_test", "mccb", "la", "fco", "earth",
                "insulation_3p", "r_dc_3p", "ratio_3p", "voltage_test_3p",
                "cap_ngam", "cap_ngam_dc"):
        if any(item.get("table") == key for item in LABELS[form]):
            warnings += TABLE_FILLERS[key](doc, values, cfg, log)

    # chữ ký
    warnings += fill_signatures(doc, tt.get("can_bo_ky_ten") or {}, cfg, log)

    # in đậm / in hoa theo cấu hình (mặc định: giữ như mẫu)
    apply_header_style(doc, form, cfg)

    # hình nền chính thống: logo công ty làm dấu chìm (mặc định bật)
    wm = cfg.get("watermark") or {}
    if wm.get("enabled", True):
        if not apply_watermark(doc, opacity=wm.get("opacity", 0.06),
                               scale=wm.get("scale", 0.62),
                               dpi=wm.get("dpi", 96)):
            warnings.append("Không tìm thấy logo trong mẫu để làm hình nền chìm")
        else:
            log("    ✓ Hình nền chìm                 = logo công ty")

    out_dir.mkdir(parents=True, exist_ok=True)
    so = norm_text(block.get("so_bien_ban") or "")
    safe_so = re.sub(r"[^0-9A-Za-z]+", "", so) or f"BB{form}"
    out_path = out_dir / f"{form}_{safe_so}{suffix}.docx"
    doc.save(str(out_path))
    return out_path, warnings


def fill_signatures(doc, people: dict, cfg: dict, log) -> list[str]:
    """Điền tên người thử / kiểm tra / P. Giám đốc vào hàng chữ ký."""
    mapping = [
        ("Người thử", people.get("nguoi_thu") or people.get("nguoi_thu_nghiem")),
        ("Kiểm tra", people.get("nguoi_kiem_tra")),
        ("P. Giám đốc", people.get("p_giam_doc") or people.get("giam_doc")),
    ]
    sig_table = None
    for t in doc.tables:
        head = flexible(" ".join(cell_text(tc) for tc in t.rows[0]._tr.findall(TC)))
        if "nguoithu" in head and "pgiamd" in head.replace("ố", "o"):
            sig_table = t
            break
    if sig_table is None:
        # mẫu 46/47: chữ ký là các đoạn văn (không nằm trong bảng)
        for p in L.iter_body_paragraphs(doc):
            t = para_text(p)
            for old, new in [
                ("Nguyễn Trung Nghĩa", people.get("nguoi_thu")),
                ("Nguyễn Minh Quân", people.get("nguoi_kiem_tra")),
                ("Nguyễn Nhật Tân", people.get("p_giam_doc") or people.get("giam_doc")),
            ]:
                if new and old in t:
                    set_para_text(p, t.replace(old, norm_text(new)))
                    t = para_text(p)
        return []
    for ci, (label, name) in enumerate(mapping):
        if not name:
            continue
        if len(sig_table.rows) < 2:
            continue
        cells = sig_table.rows[1].cells
        if ci < len(cells):
            set_para_text(_first_para(cells[ci]._tc), norm_text(name))
    log("    ✓ Người thử / Kiểm tra / P.GĐ  = " + " / ".join(
        norm_text(n) for _, n in mapping if n))
    return []


def _first_para(tc):
    ps = tc.findall(P)
    return ps[0] if ps else tc


def apply_header_style(doc, form: str, cfg: dict) -> None:
    """Lớp cuối: in đậm / in hoa các biến tiêu đề theo cấu hình.

    Mặc định (``header_values = "template"``) không làm gì — biên bản giữ đúng
    định dạng mẫu. Bật ``bold_upper`` thì chỉ giá trị bị in đậm + in hoa,
    nhãn (``Tên công trình:``) vẫn như cũ.
    """
    st = cfg.get("style") or {}
    mode = st.get("header_values", "template")
    if mode != "bold_upper" and not (
        st.get("bold_header_values") or st.get("upper_header_values")
    ):
        return
    targets = [f["label"] for f in LABELS[form]
               if f.get("style") == "header" and f.get("label")]
    for p in L.iter_text_paragraphs(doc):
        t = para_text(p)
        if not t.strip():
            continue
        for name in targets:
            if L.find_label_span(t, name):
                L.apply_style(p, "header", cfg)
                break


def render_all(
    data: dict,
    *,
    templates_dir: Path | str,
    out_dir: Path | str,
    forms: list[str] | None = None,
    cfg: dict | None = None,
    log: Callable[[str], None] = lambda s: None,
) -> tuple[list[Path], list[str]]:
    """Sinh toàn bộ biên bản có dữ liệu trong JSON."""
    cfg = cfg or load_config()
    forms = forms or list(TEMPLATES)
    paths, warnings = [], []
    extra: dict = data.get("_extra") or {}
    for form in forms:
        key = DATA_KEYS[form]
        if key not in data:
            continue
        log(f"  → Biên bản {form}: {TITLES[form]}")
        path, warns = render_form(
            form, data, templates_dir=templates_dir, out_dir=out_dir, cfg=cfg, log=log
        )
        paths.append(path)
        warnings += [f"[BB {form}] {w}" for w in warns]

        # Cùng một mẫu nhưng nhiều biên bản (VD 2 tờ LA của 2 đợt) → in thêm
        # mỗi biên bản một file, không ghi đè lên nhau.
        for i, block in enumerate(extra.get(key) or [], start=1):
            if not isinstance(block, dict) or not block:
                continue
            one = {k: v for k, v in data.items() if k != "_extra"}
            one[key] = block
            log(f"  → Biên bản {form} #{i + 1}: {block.get('so_bien_ban') or ''}")
            try:
                path2, warns2 = render_form(
                    form, one, templates_dir=templates_dir, out_dir=out_dir,
                    cfg=cfg, log=log, suffix=f"-{i + 1}")
            except Exception as exc:                        # pragma: no cover
                warnings.append(f"[BB {form}] Không in được biên bản thứ {i + 1}: {exc}")
                continue
            paths.append(path2)
            warnings += [f"[BB {form} #{i + 1}] {w}" for w in warns2]
    return paths, warnings
