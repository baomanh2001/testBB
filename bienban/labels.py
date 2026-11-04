"""Điền các ô kiểu ``Nhãn: giá trị`` trong phần thân biên bản.

Cách hoạt động
-------------
1. Duyệt tài liệu theo đúng thứ tự (bảng trước, đoạn văn sau — chính là thứ
   tự đọc của Word) và tìm câu chứa nhãn, ví dụ ``Tên công trình:``.
2. Thay **chỉ phần sau dấu hai chấm** cho tới lần xuất hiện kế tiếp của
   `` - nhãn khác:`` hoặc hết dòng. Nhờ vậy một dòng có 2–3 ô (ngăn bằng tab)
   vẫn được điền đúng ô, không bị ghi đè lẫn nhau.
3. Không đụng tới tiền tố của mẫu (``KẾT LUẬN:``, ``NGÀY:``...) → luôn chuẩn
   form; đánh số La Mã, ký tự tab, cỡ chữ, in đậm của mẫu được giữ nguyên.
"""

from __future__ import annotations

import re

from docx.oxml.ns import qn

from .normalize import flexible, norm_date, norm_number, norm_text, digits_only
from .ooxml import cell_text, para_text, set_para_text

P = qn("w:p")
TBL = qn("w:tbl")
TR = qn("w:tr")
TC = qn("w:tc")
SECTPR = qn("w:sectPr")


# --------------------------------------------------------------------------- #
# Duyệt tài liệu
# --------------------------------------------------------------------------- #
def _walk_paragraphs(el):
    """Sinh ra các ``<w:p>`` theo thứ tự tài liệu, gồm cả trong bảng."""
    for child in el:
        if child.tag == P:
            yield child
        elif child.tag == TBL:
            for tr in child.findall(TR):
                for tc in tr.findall(TC):
                    yield from _walk_paragraphs(tc)
        elif child.tag == SECTPR:
            continue
        else:
            yield from _walk_paragraphs(child)


def iter_body_paragraphs(doc):
    """Mọi ``<w:p>`` trong thân tài liệu, kể cả trong bảng (thứ tự đọc)."""
    return list(_walk_paragraphs(doc.element.body))


def iter_text_paragraphs(doc):
    """Chỉ các đoạn văn **ngoài** bảng (ô nhãn của biên bản nằm ở đây)."""
    out = []
    for child in doc.element.body:
        if child.tag == P:
            out.append(child)
        elif child.tag == TBL:
            continue
    return out


# --------------------------------------------------------------------------- #
# Nhận dạng nhãn
# --------------------------------------------------------------------------- #
def _norm_label(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[\s.]+$", "", text.strip())
    return text


def label_regex(label: str) -> re.Pattern:
    """Regex bắt ``Nhãn:`` cho phép ngắt bởi tab/khoảng trắng tuỳ ý.

    Word thường cắt chữ thành nhiều run nên khi ghép text lại, tab có thể nằm
    giữa nhãn. Ta so khớp theo *khoá không dấu* để bền với mọi biến thể.
    """
    parts = [re.escape(flexible(w)) for w in _norm_label(label).split()]
    return re.compile("".join(parts))


def find_label_span(text: str, label: str) -> tuple[int, int] | None:
    """Trả về ``(vị_trí_bắt_đầu_giá_trị, vị_trí_bắt_đầu_giá_trị)`` của nhãn.

    Chỉ coi là nhãn khi **đứng đầu từ** và **theo sau là dấu hai chấm**, nhờ
    vậy ``IN`` không khớp nhầm vào ``NGHIỆM`` và ``Hiệu`` không khớp vào
    ``Hiệu máy`` khi đang điền ``Hiệu máy``.
    """
    target = flexible(label)
    if not target:
        return None
    stripped, index_map = [], []
    for i, ch in enumerate(text):
        for sym in flexible(ch):
            stripped.append(sym)
            index_map.append(i)
    joined = "".join(stripped)
    start = 0
    while True:
        pos = joined.find(target, start)
        if pos < 0:
            return None
        text_start = index_map[pos]
        text_end = index_map[pos + len(target) - 1] + 1
        before = text[text_start - 1] if text_start > 0 else ""
        if before and (before.isalnum() or before == "_"):
            start = pos + 1
            continue
        # phải có dấu ':' sau nhãn (cho phép khoảng trắng/tab ở giữa)
        i = text_end
        while i < len(text) and text[i] in " \t":
            i += 1
        if i < len(text) and text[i] in ":：":
            i += 1
            if i < len(text) and text[i] == " ":
                i += 1
            return i, i
        start = pos + 1


# --------------------------------------------------------------------------- #
# Định dạng giá trị
# --------------------------------------------------------------------------- #
def format_value(spec: dict, raw) -> str:
    fmt = spec.get("fmt", "text")
    if raw is None:
        return ""
    if fmt == "date":
        return norm_date(raw)
    if fmt == "number":
        return norm_number(raw)
    if fmt == "digits":
        d = digits_only(raw)
        return d or norm_text(raw)
    if fmt == "pad2":
        d = digits_only(raw)
        return f"{int(d):02d}" if d else norm_text(raw)
    if fmt == "code":
        return digits_only(raw) or norm_text(raw)
    return norm_text(raw)


def apply_style(p, style: str, cfg: dict) -> None:
    """Áp quy tắc in đậm / in hoa **chỉ cho phần giá trị**, giữ nguyên nhãn.

    Mặc định ``header_values = "template"``: giữ đúng định dạng biên bản hiện
    hành của công ty. Bật ``bold_upper`` để in đậm + in hoa các biến tiêu đề
    (Tên công trình, Địa chỉ, Kết luận…) như yêu cầu ở bước trích xuất.
    """
    st = cfg.get("style", {})
    if style == "header":
        mode = st.get("header_values", "template")
        bold = bool(st.get("bold_header_values")) or mode == "bold_upper"
        upper = bool(st.get("upper_header_values")) or mode == "bold_upper"
    elif style == "value":
        bold = bool(st.get("bold_values"))
        upper = bool(st.get("upper_values"))
    else:
        return
    if not (bold or upper):
        return
    apply_style_to_value(p, bold=bold, upper=upper)


def apply_style_to_value(p, *, bold: bool = False, upper: bool = False) -> None:
    """In đậm / in hoa **phần giá trị**, tức từ sau dấu ``:`` đầu tiên.

    Nếu đoạn chưa được tách run ở ranh giới nhãn/giá trị (ví dụ dữ liệu dán
    thẳng từ ChatGPT), hàm tự tách tại dấu hai chấm để nhãn không bị in hoa.
    """
    from .ooxml import set_run_bold

    seen = False
    for r in list(p.iter(qn("w:r"))):
        t_nodes = [t for t in r.iter(qn("w:t"))]
        text = "".join(t.text or "" for t in t_nodes)
        if not seen and ":" in text:
            head, _, tail = text.partition(":")
            if t_nodes:
                t_nodes[0].text = head + ":"
                for extra in t_nodes[1:]:
                    extra.text = ""
            if tail:
                import copy as _copy

                new_run = _copy.deepcopy(r)
                for t in new_run.iter(qn("w:t")):
                    t.text = ""
                first_t = next(new_run.iter(qn("w:t")), None)
                if first_t is not None:
                    first_t.text = tail.upper() if upper else tail
                r.addnext(new_run)
                set_run_bold(new_run, bold)
                set_run_bold(r, bold)
                seen = True
                continue
            seen = True
            set_run_bold(r, bold)
            continue
        if seen:
            for t in t_nodes:
                if t.text and upper:
                    t.text = t.text.upper()
            set_run_bold(r, bold)


# --------------------------------------------------------------------------- #
# Bộ điền chính
# --------------------------------------------------------------------------- #
def _segments(text: str, labels: list[str]) -> list[tuple[str | None, int, int]]:
    """Chia một dòng thành các ô ``(nhãn, đầu_giá_trị, cuối_giá_trị)``.

    Mẫu dàn 2–3 ô trên một dòng bằng ``\\t- ``::

        Hiệu: MITSUBISHI\t- Số cực: 03

    Phần ``\\t- `` là **dấu phân cách** (giữ nguyên khi ghi lại), giá trị mỗi ô
    chỉ kéo dài tới sát dấu phân cách — nhờ vậy không bao giờ ghi đè ô bên
    cạnh và không làm mất tab dàn cột của mẫu.
    """
    spans: list[tuple[int, int]] = []
    pos = 0
    for m in re.finditer(r"\t\s*-\s*", text):
        spans.append((pos, m.start()))
        pos = m.end()
    spans.append((pos, len(text)))

    out: list[tuple[str | None, int, int]] = []
    for a, b in spans:
        chunk = text[a:b]
        hit = None
        for lbl in labels:
            span = find_label_span(chunk, lbl)
            if span is not None:
                hit = (lbl, a + span[0], b)
                break
        out.append(hit if hit else (None, a, b))
    return out


def fill_labels(doc, fields: list[dict], values: dict, cfg: dict, log) -> list[str]:
    """Điền mọi ô ``nhãn: giá trị``. Trả về danh sách cảnh báo."""
    paragraphs = iter_text_paragraphs(doc)
    texts = [para_text(p) for p in paragraphs]
    labels = [f["label"] for f in fields if "label" in f]
    warnings: list[str] = []

    for spec in fields:
        if "label" not in spec:
            continue  # ô kiểu bảng, xử lý riêng
        label = spec["label"]
        raw = _get(values, spec["path"])
        value = format_value(spec, raw)
        if not value:
            if spec.get("style") == "fixed":
                continue  # cụm cố định: giữ nguyên như mẫu
            value = spec.get("empty", cfg.get("empty_placeholder", "-"))
        found = False
        for i, text in enumerate(texts):
            if not text or label not in [seg[0] for seg in _segments(text, labels)]:
                continue
            for lbl, start, end in _segments(text, labels):
                if lbl != label:
                    continue
                sep = "" if start and text[start - 1] in " \t" else " "
                new_text = text[:start] + sep + value + text[end:]
                set_para_text(paragraphs[i], new_text)
                texts[i] = new_text
                apply_style(paragraphs[i], spec.get("style", "value"), cfg)
                log(f"    ✓ {label:<34} = {value}")
                found = True
                break
            if found:
                break
        if not found:
            warnings.append(f"Không tìm thấy ô '{label}' trong mẫu")
    return warnings


def _get(values: dict, path: str):
    """Lấy giá trị theo ``a.b.c``.

    Hỗ trợ:

    * ``a|b`` – lấy khoá đầu tiên có dữ liệu
    * tên khoá **có/không dấu** đều được (``nơi_kiểm_định`` ~ ``noi_kiem_dinh``)
    * ``a[0]`` – phần tử trong danh sách
    """
    for alt in path.split("|"):
        cur = values
        ok = True
        for part in alt.split("."):
            idx = None
            m = re.match(r"^(.*)\[(\d+)\]$", part)
            if m:
                part, idx = m.group(1), int(m.group(2))
            if isinstance(cur, dict):
                if part in cur:
                    cur = cur[part]
                else:
                    hit = next((k for k in cur if flexible(k) == flexible(part)), None)
                    if hit is None:
                        ok = False
                        break
                    cur = cur[hit]
            else:
                ok = False
                break
            if idx is not None:
                if isinstance(cur, (list, tuple)) and idx < len(cur):
                    cur = cur[idx]
                else:
                    ok = False
                    break
        if ok and cur not in (None, "", [], {}):
            return cur
    return None


def _find_table(doc, probes: list[str]):
    probes_f = [flexible(p) for p in probes]
    for t in doc.tables:
        joined = " ".join(cell_text(tc) for tc in t._tbl.iter(TC))
        hay = flexible(joined)
        if all(pr in hay for pr in probes_f):
            return t
    return None


def fill_row_table(doc, probes: list[str], values: list[str], log, label: str):
    """Điền 1 dãy số vào dòng có sẵn của bảng (giữ đúng thứ tự cột)."""
    t = _find_table(doc, probes)
    if t is None:
        return [f"Không thấy bảng {label}"]
    row = t.rows[-1]
    cells = row.cells
    # 2 ô đầu là nhãn/nấc, các ô sau là số liệu
    start = 0
    if cell_text(cells[0]._tc).strip().lower() in ("kết quả đo", "kết quả", ""):
        start = 1
    target = cells[start:]
    for cell, val in zip(target, values):
        if val in (None, ""):
            continue
        pts = cell._tc.findall(P)
        if not pts:
            continue
        set_para_text(pts[0], str(val))
    log(f"    ✓ {label:<34} = {', '.join(str(v) for v in values if v not in (None,''))}")
    if len(values) > len(target):
        return [f"Bảng {label}: thừa {len(values) - len(target)} giá trị"]
    return []


def fill_insulation_table(doc, data: dict, log) -> list[str]:
    """Bảng điện trở cách điện: R60 / R15 / Kht cho 3 đối tượng đo."""
    t = _find_table(doc, ["R60", "R15", "Kht"])
    if t is None:
        return ["Không thấy bảng 'Điện trở cách điện'"]
    order = [
        ("cao_vo_ha1", "(Cao+Vỏ) - Hạ 1"),
        ("cao_vo_ha2", "(Cao+Vỏ) - Hạ 2"),
        ("ha1_ha2", "Hạ 1 - Hạ 2"),
    ]
    warned = []
    for ri, (key, name) in enumerate(order):
        item = (data or {}).get(key, {})
        vals = [item.get("r60"), item.get("r15"), item.get("knt")]
        if ri + 1 >= len(t.rows):
            warned.append(f"Bảng R cách điện thiếu dòng '{name}'")
            continue
        cells = t.rows[ri + 1].cells
        for ci, v in enumerate(vals):
            if v in (None, ""):
                continue
            pts = cells[ci + 1]._tc.findall(P)
            if pts:
                set_para_text(pts[0], norm_number(v))
        log(f"    ✓ R cách điện {name:<20} = {' | '.join(norm_number(v) for v in vals if v not in (None,''))}")
    return warned


def fill_ratio_table(doc, data: dict, log) -> list[str]:
    """Bảng tỉ số biến áp (Cao → Hạ 1, Hạ 2), 5 nấc mỗi bên."""
    t = _find_table(doc, ["Hạ 1", "Hạ 2"])
    if t is None:
        return ["Không thấy bảng 'Tỉ số biến áp'"]
    warned = []
    ha1 = (data or {}).get("ha_1") or []
    ha2 = (data or {}).get("ha_2") or []
    # dòng cuối là 'Kết quả đo'
    row = t.rows[-1]
    cells = row.cells
    # 1 ô nhãn + 5 nấc Hạ 1 + 5 nấc Hạ 2 (mẫu 44)
    for i, v in enumerate(ha1[:5]):
        idx = 1 + i
        if idx < len(cells) and v not in (None, ""):
            pts = cells[idx]._tc.findall(P)
            if pts:
                set_para_text(pts[0], norm_number(v))
    for i, v in enumerate(ha2[:5]):
        idx = 6 + i
        if idx < len(cells) and v not in (None, ""):
            pts = cells[idx]._tc.findall(P)
            if pts:
                set_para_text(pts[0], norm_number(v))
    log(f"    ✓ Tỉ số biến áp Hạ 1            = {', '.join(norm_number(v) for v in ha1)}")
    log(f"    ✓ Tỉ số biến áp Hạ 2            = {', '.join(norm_number(v) for v in ha2)}")
    return warned
