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


def fill_insulation(doc, block: dict, cfg, log) -> list[str]:
    t = _find_table(doc, "insulation")
    if t is None:
        return ["Không tìm thấy bảng 'Điện trở cách điện' (mục 2)"]
    data = block.get("r_cach_dien_Mohm") or {}
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


def fill_mccb(doc, block: dict, cfg, log) -> list[str]:
    rows = block.get("ket_qua_thu_nghiem")
    if not rows:
        r = block.get("r_cach_dien_Mohm") or {}
        tx = block.get("r_tiep_xuc_uohm") or {}
        rows = [[
            norm_number(r.get("close") or cfg.get("defaults", {}).get("r_close", ">5000")),
            norm_number(r.get("open") or cfg.get("defaults", {}).get("r_open", ">5000")),
            norm_number(tx.get("pha_a")),
            norm_number(tx.get("pha_b")),
            norm_number(tx.get("pha_c")),
            norm_number(block.get("u_test_kV")),
            norm_number(block.get("dong_cat_s")),
            norm_text(block.get("ket_qua") or "Đạt"),
            digits_only(block.get("so_tem")),
        ]]
    table = _find_table(doc, "mccb")
    if table is None:
        return ["Không tìm thấy bảng kết quả thử nghiệm MCCB"]
    header_rows = TABLE_HEADER_ROWS["mccb"]
    # xoá dòng trống dư của mẫu (mẫu có sẵn 5 dòng STT)
    total_needed = header_rows + len(rows)
    while len(table.rows) > total_needed:
        tr = table.rows[-1]._tr
        tr.getparent().remove(tr)
    while len(table.rows) < total_needed:
        tr = copy.deepcopy(table.rows[-1]._tr)
        table.rows[-1]._tr.addnext(tr)
    for i, vals in enumerate(rows):
        ri = header_rows + i
        cells = table.rows[ri].cells
        _put(cells[0]._tc, str(i + 1), bold=True)
        for ci, v in enumerate(vals, start=1):
            if ci < len(cells):
                _put(cells[ci]._tc, v)
    log(f"    ✓ Bảng kết quả thử nghiệm       = {len(rows)} dòng")
    return []


def fill_la(doc, block: dict, cfg, log) -> list[str]:
    rows = block.get("ket_qua_thu_nghiem")
    if not rows:
        rows = [[
            norm_number(block.get("r_cach_dien_Mohm")),
            norm_number(block.get("dong_ro_uA")),
            norm_number(block.get("u_ac_tang_cao_kV")),
        ]]
    return _fill_row_table(doc, "la", rows, log, "Bảng kết quả kiểm định LA")


def fill_fco(doc, block: dict, cfg, log) -> list[str]:
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
            norm_text(block.get("ket_qua") or "Đạt"),
        ]]
    return _fill_row_table(doc, "fco", rows, log, "Bảng kết quả kiểm định FCO")


def fill_earth(doc, block: dict, cfg, log) -> list[str]:
    t = _find_table(doc, "earth")
    if t is None:
        return ["Không tìm thấy bảng kết quả đo điện trở nối đất"]
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
}


# --------------------------------------------------------------------------- #
# Kết luận
# --------------------------------------------------------------------------- #
def build_conclusion(form: str, block: dict, data: dict, cfg: dict) -> str:
    explicit = block.get("ket_luan") or block.get("kết_luận")
    if explicit:
        return norm_text(explicit)
    qty = block.get("so_luong") or 1
    qty_text = quantity_both(qty)
    device = (block.get("ten_thiet_bi") or "").strip()
    if not device:
        device = {
            "44": "máy biến áp 1 pha",
            "45": "máy cắt hạ thế (MCCB)",
            "46": "chống sét van",
            "47": "FCO",
            "48": "điện trở nối đất",
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

    # số biên bản: ưu tiên block, sau đó data
    merged = dict(data)
    merged[key] = block
    warnings += fill_frame(doc, form, merged, cfg, log)

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
                "voltage_test", "mccb", "la", "fco", "earth"):
        if any(item.get("table") == key for item in LABELS[form]):
            warnings += TABLE_FILLERS[key](doc, values, cfg, log)

    # chữ ký
    warnings += fill_signatures(doc, tt.get("can_bo_ky_ten") or {}, cfg, log)

    # in đậm / in hoa theo cấu hình (mặc định: giữ như mẫu)
    apply_header_style(doc, form, cfg)

    out_dir.mkdir(parents=True, exist_ok=True)
    so = norm_text(block.get("so_bien_ban") or "")
    safe_so = re.sub(r"[^0-9A-Za-z]+", "", so) or f"BB{form}"
    out_path = out_dir / f"{form}_{safe_so}.docx"
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
    for form in forms:
        if DATA_KEYS[form] not in data:
            continue
        log(f"  → Biên bản {form}: {TITLES[form]}")
        path, warns = render_form(
            form, data, templates_dir=templates_dir, out_dir=out_dir, cfg=cfg, log=log
        )
        paths.append(path)
        warnings += [f"[BB {form}] {w}" for w in warns]
    return paths, warnings
