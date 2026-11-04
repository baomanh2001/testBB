"""Dựng bản xem trước HTML từ file .docx vừa sinh.

Mục đích: người dùng bấm "Sinh biên bản" là thấy ngay **nội dung sẽ in ra**
(đúng nhãn, đúng số liệu, đúng bố cục bảng) trước khi tải file Word về máy.

Bản xem trước không phải trình render Word đầy đủ, nhưng giữ được những thứ
quan trọng để soát biên bản:

* logo + bảng tiêu đề (SỐ / NGÀY)
* chữ đậm/nghiêng/cỡ chữ, canh lề, thụt đầu dòng
* cách đánh số La Mã (I, II, III…), số (1, 2, 3…), gạch đầu dòng
* bảng kẻ có gộp ô (logo, header bảng, chữ ký)
* khổ A4, phông Times New Roman, dòng kẻ footer

Cách dùng::

    from bienban.preview import docx_to_html
    html = docx_to_html("output/45_50451126BBTC.docx")
"""

from __future__ import annotations

import base64
import html
import re
from pathlib import Path

import docx

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
WP_NS = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"

ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
         (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def _roman(n: int) -> str:
    out = []
    for value, sym in ROMAN:
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)


# --------------------------------------------------------------------------- #
# Đọc numbering.xml
# --------------------------------------------------------------------------- #
def _numbering(doc) -> dict[str, tuple[str, str]]:
    """``numId`` -> ``(numFmt, lvlText)`` của cấp 0."""
    result: dict[str, tuple[str, str]] = {}
    try:
        numbering = doc.part.numbering_part.element
    except Exception:  # không có numbering
        return result
    abstract: dict[str, tuple[str, str]] = {}
    for an in numbering.findall(f"{W}abstractNum"):
        aid = an.get(f"{W}abstractNumId")
        lvl = an.find(f"{W}lvl")
        if lvl is None:
            continue
        fmt = lvl.find(f"{W}numFmt")
        txt = lvl.find(f"{W}lvlText")
        abstract[aid] = (
            fmt.get(f"{W}val") if fmt is not None else "decimal",
            txt.get(f"{W}val") if txt is not None else "%1.",
        )
    for num in numbering.findall(f"{W}num"):
        nid = num.get(f"{W}numId")
        ref = num.find(f"{W}abstractNumId")
        if ref is not None and ref.get(f"{W}val") in abstract:
            result[nid] = abstract[ref.get(f"{W}val")]
    return result


# --------------------------------------------------------------------------- #
# Ảnh (logo, watermark)
# --------------------------------------------------------------------------- #
def _image_uri(doc, rid: str) -> str | None:
    try:
        part = doc.part.related_parts[rid]
    except Exception:
        return None
    mime = getattr(part, "content_type", None) or "image/png"
    return f"data:{mime};base64,{base64.b64encode(part.blob).decode()}"


def _img_html(doc, run) -> str:
    """Ảnh **inline** (logo). Ảnh floating (dấu chìm, con dấu) bỏ qua vì
    trong Word nó neo theo toạ độ trang, không thuộc ô nào."""
    out = []
    for drawing in run.iter(f"{W}drawing"):
        inline = drawing.find(f"{WP_NS}inline")
        if inline is None:
            continue  # wp:anchor -> bỏ
        blips = list(inline.iter(f"{A_NS}blip"))
        extents = list(inline.iter(f"{WP_NS}extent"))
        for i, blip in enumerate(blips):
            rid = blip.get(f"{R_NS}embed")
            if not rid:
                continue
            uri = _image_uri(doc, rid)
            if not uri:
                continue
            w_pt = h_pt = None
            if i < len(extents):
                cx = int(extents[i].get("cx", 0))
                cy = int(extents[i].get("cy", 0))
                w_pt, h_pt = cx / 12700, cy / 12700
            style = f"width:{w_pt:.1f}pt;height:{h_pt:.1f}pt" if w_pt and h_pt else "max-width:120px"
            out.append(f'<img src="{uri}" style="{style};vertical-align:middle" alt="logo"/>')
    return "".join(out)


# --------------------------------------------------------------------------- #
# Run / paragraph -> HTML
# --------------------------------------------------------------------------- #
def _run_style(run) -> str:
    rpr = run.find(f"{W}rPr")
    css = []
    if rpr is not None:
        if rpr.find(f"{W}b") is not None:
            css.append("font-weight:700")
        if rpr.find(f"{W}i") is not None:
            css.append("font-style:italic")
        if rpr.find(f"{W}u") is not None:
            css.append("text-decoration:underline")
        sz = rpr.find(f"{W}sz")
        if sz is not None and sz.get(f"{W}val"):
            css.append(f"font-size:{int(sz.get(f'{W}val')) / 2:.1f}pt")
    return ";".join(css)


def _tab_stops(p) -> list[int]:
    ppr = p.find(f"{W}pPr")
    stops = []
    if ppr is not None:
        tabs = ppr.find(f"{W}tabs")
        if tabs is not None:
            for t in tabs.findall(f"{W}tab"):
                pos = t.get(f"{W}pos")
                if pos and pos.lstrip("-").isdigit():
                    stops.append(int(pos))
    return sorted(stops)


def _p_style(p) -> str:
    ppr = p.find(f"{W}pPr")
    css = []
    if ppr is not None:
        jc = ppr.find(f"{W}jc")
        if jc is not None:
            mapping = {"center": "center", "right": "right", "both": "justify",
                       "distribute": "justify", "left": "left"}
            css.append(f"text-align:{mapping.get(jc.get(f'{W}val'), 'left')}")
        ind = ppr.find(f"{W}ind")
        if ind is not None:
            left = ind.get(f"{W}left") or ind.get(f"{W}start")
            if left and left.lstrip("-").isdigit():
                css.append(f"margin-left:{int(left) / 20:.1f}pt")
            hang = ind.get(f"{W}hanging")
            if hang and hang.lstrip("-").isdigit():
                css.append(f"text-indent:-{int(hang) / 20:.1f}pt")
        sp = ppr.find(f"{W}spacing")
        if sp is not None:
            before = sp.get(f"{W}before")
            after = sp.get(f"{W}after")
            if before and before.lstrip("-").isdigit():
                css.append(f"margin-top:{int(before) / 20:.1f}pt")
            if after and after.lstrip("-").isdigit():
                css.append(f"margin-bottom:{int(after) / 20:.1f}pt")
    return ";".join(css)


def _para_html(doc, p, numbering, counters) -> tuple[str, str]:
    """Trả về ``(tiền_tố_đánh_số, html)`` cho một đoạn."""
    ppr = p.find(f"{W}pPr")
    prefix = ""
    if ppr is not None:
        numpr = ppr.find(f"{W}numPr")
        if numpr is not None:
            nid_el = numpr.find(f"{W}numId")
            ilvl_el = numpr.find(f"{W}ilvl")
            nid = nid_el.get(f"{W}val") if nid_el is not None else None
            ilvl = ilvl_el.get(f"{W}val") if ilvl_el is not None else "0"
            if nid and nid != "0":
                fmt, lvl_text = numbering.get(nid, ("decimal", "%1."))
                key = (nid, ilvl)
                counters[key] = counters.get(key, 0) + 1
                n = counters[key]
                if fmt == "bullet":
                    prefix = lvl_text if lvl_text not in ("", "%1") else "-"
                elif fmt == "upperRoman":
                    prefix = _roman(n) + "."
                elif fmt == "lowerRoman":
                    prefix = _roman(n).lower() + "."
                else:
                    prefix = f"{n}."
                prefix += " "

    stops = _tab_stops(p)
    default_stop = 720  # 0.5 inch
    cursor = 0.0
    chunks: list[str] = []
    for child in p:
        if child.tag == f"{W}r":
            # ảnh
            img = _img_html(doc, child)
            if img:
                chunks.append(img)
                continue
            style = _run_style(child)
            for node in child:
                if node.tag == f"{W}t":
                    text = node.text or ""
                    if not text:
                        continue
                    esc = html.escape(text).replace("\n", "<br/>")
                    chunks.append(f'<span style="{style}">{esc}</span>' if style else esc)
                    # ước lượng bề rộng để căn tab (Times New Roman ~0.5em/ký tự)
                    size = 12.0
                    m = re.search(r"font-size:([\d.]+)pt", style)
                    if m:
                        size = float(m.group(1))
                    width = int(size * 20 * 0.5)
                    cursor += len(text) * width
                elif node.tag == f"{W}tab":
                    target = next((s for s in stops if s > cursor), None)
                    if target is None:
                        step = (stops[-1] if stops else default_stop)
                        target = cursor + step
                    gap = max(target - cursor, 0) / 20.0
                    chunks.append(f'<span style="display:inline-block;width:{gap:.1f}pt"></span>')
                    cursor = target
                elif node.tag == f"{W}br":
                    chunks.append("<br/>")
    inner = "".join(chunks)
    if not inner.strip() and not prefix:
        return "", '<p style="margin:0;height:6pt"></p>'
    css = ";".join(x for x in [_p_style(p)] if x)
    return prefix, f'<p style="{css}">{prefix if prefix else ""}{inner}</p>'


def _cell_parts(doc, tc, numbering, counters):
    """``(html, gridSpan, vMerge: 'restart'|'continue'|None)`` cho một ô."""
    span, merge = 1, None
    tcpr = tc.find(f"{W}tcPr")
    if tcpr is not None:
        gs = tcpr.find(f"{W}gridSpan")
        if gs is not None and str(gs.get(f"{W}val", "")).isdigit():
            span = int(gs.get(f"{W}val"))
        vm = tcpr.find(f"{W}vMerge")
        if vm is not None:
            merge = "restart" if vm.get(f"{W}val") == "restart" else "continue"
    parts = []
    for p in tc.findall(f"{W}p"):
        _, para = _para_html(doc, p, numbering, counters)
        if para:
            parts.append(para)
    return "".join(parts), span, merge


def _table_html(doc, tbl, numbering, counters) -> str:
    """Dựng ``<table>`` có gộp ô ngang (colspan) và dọc (rowspan)."""
    grid = tbl.find(f"{W}tblGrid")
    widths = []
    if grid is not None:
        for col in grid.findall(f"{W}gridCol"):
            w = col.get(f"{W}w")
            if w and w.isdigit():
                widths.append(int(w))

    trs = tbl.findall(f"{W}tr")
    rendered: list[list[dict]] = []      # mỗi dòng: các ô cần in
    open_merge: dict[int, dict] = {}     # cột -> ô đang gộp dọc

    for tr in trs:
        col = 0
        row_cells: list[dict] = []
        for tc in tr.findall(f"{W}tc"):
            content, span, merge = _cell_parts(doc, tc, numbering, counters)
            covered = range(col, col + span)
            if merge == "continue":
                # kéo dài ô đang mở ở các cột này
                for c in covered:
                    target = open_merge.get(c)
                    if target is not None:
                        target["rowspan"] += 1
                col += span
                continue
            cell = {"html": content, "colspan": span, "rowspan": 1}
            if merge == "restart":
                for c in covered:
                    open_merge[c] = cell
            else:
                for c in covered:
                    open_merge.pop(c, None)
            row_cells.append(cell)
            col += span
        rendered.append(row_cells)

    html_rows = []
    for row in rendered:
        tds = []
        for cell in row:
            attrs = ""
            if cell["colspan"] > 1:
                attrs += f' colspan="{cell["colspan"]}"'
            if cell["rowspan"] > 1:
                attrs += f' rowspan="{cell["rowspan"]}"'
            if cell["rowspan"] > 1:
                attrs += ' style="vertical-align:middle"'
            tds.append(f"<td{attrs}>{cell['html']}</td>")
        html_rows.append(f"<tr>{''.join(tds)}</tr>")

    cols = "".join(f'<col style="width:{w / 20:.1f}pt"/>' for w in widths) if widths else ""
    return f'<table class="doc-tbl"><colgroup>{cols}</colgroup>{"".join(html_rows)}</table>'


# --------------------------------------------------------------------------- #
# API chính
# --------------------------------------------------------------------------- #
def docx_to_html(source: str | Path | bytes, *, title: str = "", footer: str = "") -> str:
    """Chuyển .docx (đường dẫn hoặc bytes) thành một khối HTML xem trước."""
    import io

    if isinstance(source, bytes):
        doc = docx.Document(io.BytesIO(source))
    else:
        doc = docx.Document(str(source))

    numbering = _numbering(doc)
    counters: dict[tuple[str, str], int] = {}
    body: list[str] = []

    for child in doc.element.body:
        if child.tag == f"{W}p":
            _, para = _para_html(doc, child, numbering, counters)
            if para:
                body.append(para)
        elif child.tag == f"{W}tbl":
            body.append(_table_html(doc, child, numbering, counters))

    # footer (địa chỉ, hotline, website) – hiển thị mờ ở cuối trang
    footer_text = footer
    if not footer_text:
        try:
            for sec in doc.sections:
                texts = [p.text.strip() for p in sec.footer.paragraphs if p.text.strip()]
                if texts:
                    footer_text = " · ".join(texts)
                    break
        except Exception:
            footer_text = ""

    return f"""<div class="page">
  <div class="page-body">{''.join(body)}</div>
  {f'<div class="page-foot">{html.escape(footer_text)}</div>' if footer_text else ''}
</div>"""


PAGE_CSS = """
.page{background:#fff;color:#000;width:21cm;min-height:29.7cm;margin:0 auto;
      padding:1cm 1.2cm 1.6cm;box-shadow:0 8px 30px rgba(0,0,0,.45);
      font-family:"Times New Roman","Liberation Serif",serif;font-size:12pt;
      line-height:1.28;position:relative;box-sizing:border-box}
.page-body p{margin:3pt 0}
.doc-tbl{border-collapse:collapse;width:100%;margin:5pt 0;table-layout:fixed}
.doc-tbl td{border:1px solid #000;padding:2pt 4pt;font-size:10pt;text-align:center;
            vertical-align:middle;overflow-wrap:anywhere}
.doc-tbl td p{margin:0;text-align:center}
.page-foot{position:absolute;left:1.2cm;right:1.2cm;bottom:.7cm;font-size:8.5pt;
           color:#555;border-top:1px solid #bbb;padding-top:3pt;text-align:center}
"""
