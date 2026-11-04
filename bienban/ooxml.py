"""Tiện ích đọc/ghi file Word.

Nguyên tắc: **chỉ sửa đúng phần chữ**, không dựng lại tài liệu. Logo, header,
footer, khung trang, watermark, bảng kẻ, chữ ký số... của file mẫu được giữ
nguyên 100%. Nhờ vậy biên bản sinh ra mở bằng Word vẫn "chuẩn form" như mẫu
gốc của công ty.
"""

from __future__ import annotations

import copy

from docx.oxml.ns import qn
from docx.oxml import OxmlElement

W_P = qn("w:p")
W_R = qn("w:r")
W_T = qn("w:t")
W_TBL = qn("w:tbl")
W_TR = qn("w:tr")
W_TC = qn("w:tc")
W_TAB = qn("w:tab")


# --------------------------------------------------------------------------- #
# Đọc chữ
# --------------------------------------------------------------------------- #
def para_text(p) -> str:
    """Lấy text của ``<w:p>``: tab ký tự -> ``\\t``; bỏ qua tab-stop trong ``pPr``."""
    out: list[str] = []
    skip = {qn("w:pPr"), qn("w:tabs")}

    def walk(el):
        tag = el.tag
        if tag in skip:
            return
        if tag == W_T:
            out.append(el.text or "")
        elif tag == W_TAB:
            out.append("\t")
        elif tag == qn("w:br"):
            out.append("\n")
        for child in el:
            walk(child)

    walk(p)
    return "".join(out)


def cell_text(tc) -> str:
    return " ".join(
        para_text(p).strip() for p in tc.findall(W_P) if para_text(p).strip()
    )


# --------------------------------------------------------------------------- #
# Ghi chữ (giữ nguyên định dạng của run gốc)
# --------------------------------------------------------------------------- #
def _mk_run(template_r, text: str):
    r = OxmlElement("w:r")
    if template_r is not None and template_r.find(qn("w:rPr")) is not None:
        r.append(copy.deepcopy(template_r.find(qn("w:rPr"))))
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    r.append(t)
    return r


def _mk_tab_run(template_r):
    r = OxmlElement("w:r")
    if template_r is not None and template_r.find(qn("w:rPr")) is not None:
        r.append(copy.deepcopy(template_r.find(qn("w:rPr"))))
    r.append(OxmlElement("w:tab"))
    return r


def _first_content_run(p):
    for r in p.iter(W_R):
        if r.find(W_T) is not None or r.find(W_TAB) is not None:
            return r
    return None


def _drop_no_proof(p):
    for tag in ("w:proofErr", "w:bookmarkStart", "w:bookmarkEnd"):
        for el in list(p.iter(qn(tag))):
            parent = el.getparent()
            if parent is not None and parent.tag == W_P:
                parent.remove(el)


def set_para_text(p, text: str, bold: bool | None = None, upper: bool = False,
                  preserve_lead_space: bool = True) -> None:
    """Thay toàn bộ chữ của một đoạn, giữ định dạng chữ (cỡ, font) của đoạn mẫu.

    Ký tự tab trong ``text`` được ghi lại thành ``<w:tab/>`` để các ô dàn bằng
    tab của mẫu (``Hiệu: ...\\t- Số cực: ...``) không bị dồn thành một dòng.

    Đoạn được tách thành **run nhãn** (tới dấu ``:``) và **run giá trị** — nhờ
    vậy bước in đậm / in hoa sau đó chỉ tác động lên giá trị, còn nhãn giữ
    nguyên như mẫu.

    ``bold``: ``True`` bật in đậm, ``False`` tắt in đậm, ``None`` giữ như mẫu.
    """
    template_r = _first_content_run(p)
    for child in list(p):
        if child.tag != qn("w:pPr"):
            p.remove(child)
    _drop_no_proof(p)

    payload = text.upper() if upper else text
    pieces: list[tuple[str, bool]] = []  # (chữ, là_giá_trị?)
    for i, chunk in enumerate(payload.split("\t")):
        if i:
            pieces.append(("\t", False))
        if not chunk:
            continue
        if ":" in chunk:
            head, _, tail = chunk.partition(":")
            pieces.append((head + ":", False))
            if tail:
                pieces.append((tail, True))
        else:
            pieces.append((chunk, pieces[-1][1] if pieces else False))

    for chunk, is_value in pieces:
        if chunk == "\t":
            p.append(_mk_tab_run(template_r))
            continue
        if ":" in chunk and not is_value:
            head, _, tail = chunk.partition(":")
            p.append(_mk_run(template_r, head + ":"))
            if tail:
                p.append(_mk_run(template_r, tail))
        else:
            p.append(_mk_run(template_r, chunk))

    if bold is True:
        set_para_bold(p, True)
    elif bold is False:
        set_para_bold(p, False)


def set_run_bold(r, bold: bool) -> None:
    """Bật/tắt in đậm cho một run."""
    rpr = r.find(qn("w:rPr"))
    if rpr is None:
        rpr = OxmlElement("w:rPr")
        r.insert(0, rpr)
    _set_bold_flag(rpr, bold)


def set_para_bold(p, bold: bool) -> None:
    """Bật/tắt in đậm cho mọi run (và cho pPr/rPr để run mới cũng theo)."""
    for r in p.iter(W_R):
        rpr = r.find(qn("w:rPr"))
        if rpr is None:
            rpr = OxmlElement("w:rPr")
            r.insert(0, rpr)
        _set_bold_flag(rpr, bold)
    ppr = p.find(qn("w:pPr"))
    if ppr is not None:
        rpr = ppr.find(qn("w:rPr"))
        if rpr is None:
            rpr = OxmlElement("w:rPr")
            ppr.append(rpr)
        _set_bold_flag(rpr, bold)


def _set_bold_flag(rpr, bold: bool) -> None:
    for tag in ("w:b", "w:bCs"):
        el = rpr.find(qn(tag))
        if bold:
            if el is None:
                el = OxmlElement(tag)
                rpr.insert(0, el)
            el.set(qn("w:val"), "1")
        elif el is not None:
            rpr.remove(el)


def set_runs_text(p, start: int, end: int, new_text: str) -> None:
    """Giữ ``[0:start]`` của text, thay ``[start:end]`` bằng ``new_text``.

    Dùng khi ta chỉ muốn đổi phần *giá trị* mà vẫn giữ nguyên nhãn + tab.
    """
    old = para_text(p)
    set_para_text(p, old[:start] + new_text + old[end:])


def replace_text_in_paragraph(p, needle: str, replacement: str) -> bool:
    """Thay ``needle`` bằng ``replacement`` trong text của đoạn (giữ layout).

    Thay ở mức *byte chữ*: dồn các run lại để xử lý trường hợp ``needle`` bị
    cắt qua nhiều run (lỗi rất thường gặp khi mở file Word thật).
    """
    old = para_text(p)
    idx = old.find(needle)
    if idx < 0:
        return False
    set_para_text(p, old[:idx] + replacement + old[idx + len(needle):])
    return True


def insert_paragraph_after(p, text: str, clone_from=None):
    """Chèn một đoạn mới ngay sau ``p`` (dùng chung pPr của đoạn mẫu)."""
    new_p = OxmlElement("w:p")
    src = clone_from if clone_from is not None else p
    ppr = src.find(qn("w:pPr"))
    if ppr is not None:
        new_p.append(copy.deepcopy(ppr))
    new_p.append(_mk_run(_first_content_run(src), text))
    p.addnext(new_p)
    return new_p


# --------------------------------------------------------------------------- #
# Bảng
# --------------------------------------------------------------------------- #
def find_table(doc, header_texts: list[str], required: int = 1):
    """Tìm bảng có đủ các tiêu đề (không phân biệt hoa/thường, dấu)."""
    from .normalize import flexible

    want = [flexible(h) for h in header_texts]
    for t in doc.tables:
        rows = t.rows
        if len(rows) < required:
            continue
        joined = " | ".join(cell_text(tc) for tc in rows[0]._tr.findall(W_TC))
        joined += " | " + " | ".join(
            cell_text(tc) for tc in (rows[1]._tr.findall(W_TC) if len(rows) > 1 else [])
        )
        have = flexible(joined)
        if all(w in have for w in want):
            return t
    return None


def grid_cells(t):
    """Danh sách ô theo đúng cột lưới của bảng (đã bung ô gộp ngang)."""
    grid = []
    ncols = len(t.columns)
    for row in t.rows:
        cells = []
        tr = row._tr
        for tc in tr.findall(W_TC):
            span = tc.find(qn("w:tcPr") + "/" + qn("w:gridSpan"))
            width = int(span.get(qn("w:val"))) if span is not None else 1
            cells.append((tc, width))
        expanded = []
        for tc, width in cells:
            expanded.extend([tc] * width)
        while len(expanded) < ncols:
            expanded.append(None)
        grid.append(expanded[:ncols])
    return grid


def cell_paragraph(tc, idx: int = 0):
    ps = tc.findall(W_P)
    while len(ps) <= idx:
        new_p = OxmlElement("w:p")
        tc.append(new_p)
        ps.append(new_p)
    return ps[idx]


def set_cell_text(tc, text: str, bold: bool | None = None, upper: bool = False) -> None:
    """Ghi giá trị vào ô: chữ thường, canh giữa, giữ cỡ chữ của mẫu."""
    p = cell_paragraph(tc, 0)
    # xoá các đoạn thừa
    for extra in tc.findall(W_P)[1:]:
        tc.remove(extra)
    set_para_text(p, text, bold=bold, upper=upper)


def ensure_rows(t, count: int):
    """Đảm bảo bảng có ít nhất ``count`` dòng (nhân bản dòng cuối nếu thiếu)."""
    while len(t.rows) < count:
        last = t.rows[-1]._tr
        t._tbl.append(copy.deepcopy(last))


def repeat_row(t, template_row: int, times: int):
    """Nhân bản dòng mẫu thêm ``times`` dòng, chèn ngay sau nó."""
    row = t.rows[template_row]._tr
    anchor = row
    for _ in range(times):
        new = copy.deepcopy(row)
        anchor.addnext(new)
        anchor = new
    return anchor


def remove_row(t, index: int) -> None:
    tr = t.rows[index]._tr
    tr.getparent().remove(tr)


def set_col_widths(t, widths_twips: list[int]) -> None:
    """Ép lại độ rộng cột (dùng khi phải thêm cột)."""
    grid = t._tbl.find(qn("w:tblGrid"))
    cols = grid.findall(qn("w:gridCol"))
    for col, w in zip(cols, widths_twips):
        col.set(qn("w:w"), str(w))
    for row in t.rows:
        for tc, w in zip(row._tr.findall(W_TC), widths_twips):
            tcw = tc.find(qn("w:tcPr") + "/" + qn("w:tcW"))
            if tcw is not None:
                tcw.set(qn("w:w"), str(w))


def add_column(t, after_index: int, width_twips: int = 1000):
    """Thêm một cột rỗng (header + mọi dòng) phía sau cột ``after_index``."""
    for row in t.rows:
        tcs = row._tr.findall(W_TC)
        if after_index >= len(tcs):
            continue
        new_tc = copy.deepcopy(tcs[after_index])
        # xoá nội dung chữ để tránh lặp
        for p in new_tc.findall(W_P):
            new_tc.remove(p)
        new_tc.append(OxmlElement("w:p"))
        tcw = new_tc.find(qn("w:tcPr") + "/" + qn("w:tcW"))
        if tcw is not None:
            tcw.set(qn("w:w"), str(width_twips))
        tcs[after_index].addnext(new_tc)
    grid = t._tbl.find(qn("w:tblGrid"))
    cols = grid.findall(qn("w:gridCol"))
    new_col = copy.deepcopy(cols[after_index])
    new_col.set(qn("w:w"), str(width_twips))
    cols[after_index].addnext(new_col)


def set_doc_simple_field(doc, instr: str, value: str) -> int:
    """Thay nội dung ``fldSimple`` (nếu template dùng field kiểu Word)."""
    count = 0
    for fld in doc.element.body.iter(qn("w:fldSimple")):
        if instr.lower() in (fld.get(qn("w:instr")) or "").lower():
            ts = list(fld.iter(W_T))
            if ts:
                ts[0].text = value
                for extra in ts[1:]:
                    extra.text = ""
                count += 1
    return count
