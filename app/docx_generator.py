import base64
import copy
import io
import os
import zipfile
from typing import Dict, List, Optional, Tuple, Union
from lxml import etree
from pydantic import BaseModel
from typing import get_args, get_origin

from app.schemas import (
    CapNgamData,
    DtndData,
    FcoData,
    LaData,
    Mba1PData,
    Mba3PData,
    MccbData,
    ReportDocumentRequest,
    TuBuData,
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

RunSpec = Union[Tuple[str, bool], Tuple[str, bool, Optional[str]]]


def _read_data(model: type[BaseModel], values: dict) -> BaseModel:
    """Missing observations must never be filled with values from example schemas."""
    clean = {}
    for name, field in model.model_fields.items():
        annotation = field.annotation
        if get_origin(annotation) is list:
            item_type = get_args(annotation)[0]
            rows = values.get(name, [])
            if isinstance(item_type, type) and issubclass(item_type, BaseModel):
                clean[name] = [_read_data(item_type, row if isinstance(row, dict) else {}) for row in rows]
            else:
                clean[name] = rows
        else:
            value = values.get(name, "")
            clean[name] = "" if value is None else value
    return model(**clean)


def _w(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def _make_run(text: str, bold: bool = False, sz: int = 24, vert_align: Optional[str] = None) -> etree._Element:
    r = etree.Element(_w("r"))
    rPr = etree.SubElement(r, _w("rPr"))
    rFonts = etree.SubElement(rPr, _w("rFonts"))
    rFonts.set(_w("ascii"), "Times New Roman")
    rFonts.set(_w("hAnsi"), "Times New Roman")
    rFonts.set(_w("cs"), "Times New Roman")
    if bold:
        etree.SubElement(rPr, _w("b"))
        etree.SubElement(rPr, _w("bCs"))
    sz_el = etree.SubElement(rPr, _w("sz"))
    sz_el.set(_w("val"), str(sz))
    szCs_el = etree.SubElement(rPr, _w("szCs"))
    szCs_el.set(_w("val"), str(sz))
    if vert_align:
        va = etree.SubElement(rPr, _w("vertAlign"))
        va.set(_w("val"), vert_align)

    lines = text.split("\n")
    for l_idx, line in enumerate(lines):
        if l_idx > 0:
            etree.SubElement(r, _w("br"))
        parts = line.split("\t")
        for idx, part in enumerate(parts):
            if idx > 0:
                etree.SubElement(r, _w("tab"))
            if part:
                t = etree.SubElement(r, _w("t"))
                if part.startswith(" ") or part.endswith(" "):
                    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                t.text = part
    return r


def set_p_runs(
    p: etree._Element,
    runs: List[RunSpec],
    sz: int = 24,
    keep_drawings: bool = False,
) -> None:
    preserved = []
    for ch in list(p):
        tag = ch.tag.split("}")[-1]
        if tag == "pPr":
            preserved.append(ch)
        elif keep_drawings and ch.find(f".//{{{W_NS}}}drawing") is not None:
            preserved.append(ch)
        p.remove(ch)

    for el in preserved:
        p.append(el)

    for spec in runs:
        if len(spec) == 2:
            txt, b = spec
            va = None
        else:
            txt, b, va = spec
        p.append(_make_run(txt, bold=b, sz=sz, vert_align=va))


def set_tc_runs(
    tc: etree._Element,
    runs: List[RunSpec],
    sz: int = 24,
    align: Optional[str] = "center",
    keep_drawings: bool = False,
) -> None:
    ps = tc.findall("w:p", NS)
    if not ps:
        p = etree.SubElement(tc, _w("p"))
    else:
        p = ps[0]
        if not keep_drawings:
            for extra_p in ps[1:]:
                tc.remove(extra_p)
    pPr = p.find("w:pPr", NS)
    if pPr is None:
        pPr = etree.Element(_w("pPr"))
        p.insert(0, pPr)
    if align:
        jc = pPr.find("w:jc", NS)
        if jc is None:
            jc = etree.SubElement(pPr, _w("jc"))
        jc.set(_w("val"), align)
    set_p_runs(p, runs, sz=sz, keep_drawings=keep_drawings)


def update_header_table(tbl: etree._Element, req: ReportDocumentRequest, default_doc_title: str) -> None:
    rows = tbl.findall("w:tr", NS)
    r0_cells = rows[0].findall("w:tc", NS)
    r1_cells = rows[1].findall("w:tc", NS)

    ten_cty = req.company.ten_cong_ty or "CÔNG TY CP THÍ NGHIỆM ĐIỆN TOÀN CẦU"
    loai_td = req.common.loai_tieu_de or default_doc_title

    set_tc_runs(r0_cells[1], [(ten_cty, True)], sz=26, align="center")
    set_tc_runs(r0_cells[2], [("SỐ: ", True), (req.common.so_bien_ban, False)], sz=22, align="left")
    set_tc_runs(r1_cells[1], [(loai_td, True)], sz=32, align="center")
    set_tc_runs(r1_cells[2], [("NGÀY: ", True), (req.common.ngay_phat_hanh, False)], sz=22, align="left")


def update_table_signature(tbl: etree._Element, req: ReportDocumentRequest) -> None:
    rows = tbl.findall("w:tr", NS)
    r0_cells = rows[0].findall("w:tc", NS)
    r1_cells = rows[1].findall("w:tc", NS)

    ps0 = r0_cells[0].findall("w:p", NS)
    if ps0:
        set_p_runs(ps0[0], [("Người thử", True)], sz=24, keep_drawings=True)
        if not req.signatory.include_signature:
            for extra_p in ps0[1:]:
                for dr in extra_p.findall(f".//{{{W_NS}}}drawing"):
                    parent = dr.getparent()
                    if parent is not None:
                        parent.remove(dr)

    set_tc_runs(r0_cells[1], [("Kiểm tra", True)], sz=24, align="center")
    set_tc_runs(r0_cells[2], [("P. Giám đốc", True)], sz=24, align="center")

    set_tc_runs(r1_cells[0], [(req.signatory.nguoi_thu, True)], sz=24, align="center")
    set_tc_runs(r1_cells[1], [(req.signatory.kiem_tra, True)], sz=24, align="center")
    set_tc_runs(r1_cells[2], [(req.signatory.pho_giam_doc, True)], sz=24, align="center")


def update_paragraph_signature(
    p_titles: etree._Element,
    p_names: etree._Element,
    req: ReportDocumentRequest,
) -> None:
    set_p_runs(
        p_titles,
        [("\tNgười thử\tKiểm tra\tP. Giám đốc", True)],
        sz=24,
        keep_drawings=req.signatory.include_signature,
    )
    pPr = p_names.find("w:pPr", NS)
    if pPr is not None:
        tabs = pPr.find("w:tabs", NS)
        if tabs is not None:
            tab_list = tabs.findall("w:tab", NS)
            if tab_list:
                tab_list[0].set(_w("pos"), "1276")
    set_p_runs(
        p_names,
        [(f"\t{req.signatory.nguoi_thu}\t{req.signatory.kiem_tra}\t{req.signatory.pho_giam_doc}", True)],
        sz=24,
    )


def populate_dynamic_rows(
    tbl: etree._Element,
    header_row_count: int,
    row_values: List[List[str]],
    sz: int = 24,
    left_align_cols: Optional[set] = None,
    vmerge_col: Optional[int] = None,
) -> None:
    left_align_cols = left_align_cols or set()
    all_rows = tbl.findall("w:tr", NS)
    template_row = copy.deepcopy(all_rows[-1])
    # Clear any inherited vMerge from template_row
    for tc in template_row.findall("w:tc", NS):
        tcPr = tc.find("w:tcPr", NS)
        if tcPr is not None:
            for vm in tcPr.findall("w:vMerge", NS):
                tcPr.remove(vm)

    for r in all_rows[header_row_count:]:
        tbl.remove(r)

    if not row_values:
        row_values = [["" for _ in template_row.findall("w:tc", NS)]]

    prev_merge_val = None
    for row_idx, vals in enumerate(row_values):
        new_tr = copy.deepcopy(template_row)
        cells = new_tr.findall("w:tc", NS)
        for ci, tc in enumerate(cells):
            val = vals[ci] if ci < len(vals) else ""
            align = "left" if ci in left_align_cols else "center"

            if vmerge_col is not None and ci == vmerge_col:
                tcPr = tc.find("w:tcPr", NS)
                if tcPr is None:
                    tcPr = etree.Element(_w("tcPr"))
                    tc.insert(0, tcPr)
                if row_idx > 0 and val != "" and val == prev_merge_val:
                    etree.SubElement(tcPr, _w("vMerge"))
                    set_tc_runs(tc, [("", False)], sz=sz, align=align)
                else:
                    vm = etree.SubElement(tcPr, _w("vMerge"))
                    vm.set(_w("val"), "restart")
                    set_tc_runs(tc, [(str(val), False)], sz=sz, align=align)
                    prev_merge_val = val
            else:
                set_tc_runs(tc, [(str(val), False)], sz=sz, align=align)
        tbl.append(new_tr)


def _decode_custom_signature(data_url: Optional[str]) -> Optional[bytes]:
    if not data_url:
        return None
    b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
    try:
        return base64.b64decode(b64)
    except Exception:
        return None


def _roman_number(number: int) -> str:
    parts = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
             (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
             (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))
    result = []
    for value, text in parts:
        count, number = divmod(number, value)
        result.append(text * count)
    return "".join(result)


def _materialize_body_numbering(root: etree._Element, numbering_xml: bytes) -> None:
    """Make the template's list labels literal, so Word and HTML agree on them.

    The supplied templates use single-level Roman, decimal and hyphen lists.
    Preserve their paragraph indentation and other tabs; replace only supported
    body list labels, leaving any other numbering untouched.
    """
    numbering = etree.fromstring(numbering_xml)
    definitions = {}
    for num in numbering.findall("w:num", NS):
        num_id = num.get(_w("numId"))
        abstract_id = num.find("w:abstractNumId", NS)
        if abstract_id is None:
            continue
        abstract = numbering.find(f"w:abstractNum[@w:abstractNumId='{abstract_id.get(_w('val'))}']", NS)
        if abstract is None:
            continue
        level = abstract.find("w:lvl[@w:ilvl='0']", NS)
        if level is None:
            continue
        fmt = level.find("w:numFmt", NS)
        text = level.find("w:lvlText", NS)
        start = level.find("w:start", NS)
        override = num.find("w:lvlOverride[@w:ilvl='0']/w:startOverride", NS)
        definitions[num_id] = (
            fmt.get(_w("val")) if fmt is not None else "",
            text.get(_w("val")) if text is not None else "",
            int((override if override is not None else start).get(_w("val"), "1")) if override is not None or start is not None else 1,
        )

    counters = {}
    for paragraph in root.findall("w:body/w:p", NS):
        ppr = paragraph.find("w:pPr", NS)
        numpr = ppr.find("w:numPr", NS) if ppr is not None else None
        if numpr is None:
            continue
        num = numpr.find("w:numId", NS)
        level = numpr.find("w:ilvl", NS)
        if num is None or (level is not None and level.get(_w("val")) != "0"):
            continue
        num_id = num.get(_w("val"))
        fmt, text, start = definitions.get(num_id, ("", "", 1))
        if fmt == "bullet" and text == "-":
            label = "-"
        elif fmt in ("upperRoman", "decimal") and text == "%1.":
            count = counters.get(num_id, start)
            counters[num_id] = count + 1
            label = (_roman_number(count) if fmt == "upperRoman" else str(count)) + "."
        else:
            continue

        # Insert a real number/bullet as text, retaining the original run style.
        ppr.remove(numpr)
        first_run = paragraph.find("w:r", NS)
        run = _make_run(label + "\t", bold=False)
        old_properties = first_run.find("w:rPr", NS) if first_run is not None else None
        if old_properties is not None:
            run.replace(run.find("w:rPr", NS), copy.deepcopy(old_properties))
        paragraph.insert(list(paragraph).index(first_run) if first_run is not None else len(paragraph), run)

        # List-label tabs used to be implicit in Word's numbering properties.
        # Add an explicit stop at the existing left indent, without changing
        # the second-column stops already present in the template.
        ind = ppr.find("w:ind", NS)
        left = ind.get(_w("left")) if ind is not None else None
        if left and int(left) > 0:
            tabs = ppr.find("w:tabs", NS)
            if tabs is None:
                tabs = etree.Element(_w("tabs"))
                insert_at = next((i for i, el in enumerate(ppr) if el.tag in {_w("spacing"), _w("ind"), _w("jc"), _w("rPr")}), len(ppr))
                ppr.insert(insert_at, tabs)
            if not any(t.get(_w("pos")) == left for t in tabs.findall("w:tab", NS)):
                tab = etree.Element(_w("tab"))
                tab.set(_w("val"), "left")
                tab.set(_w("pos"), left)
                tabs.insert(0, tab)


def _repack_docx(
    template_path: str,
    doc_xml_root: etree._Element,
    custom_sig_bytes: Optional[bytes] = None,
    extra_xml_overrides: Optional[Dict[str, bytes]] = None,
) -> bytes:
    extra_xml_overrides = extra_xml_overrides or {}
    out_buf = io.BytesIO()
    with zipfile.ZipFile(template_path, "r") as zin, zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
        _materialize_body_numbering(doc_xml_root, zin.read("word/numbering.xml"))
        doc_bytes = etree.tostring(doc_xml_root, xml_declaration=True, encoding="UTF-8", standalone="yes")
        for item in zin.infolist():
            fname = item.filename
            if fname == "word/document.xml":
                zout.writestr(item, doc_bytes)
            elif fname in extra_xml_overrides:
                zout.writestr(item, extra_xml_overrides[fname])
            elif fname == "word/media/image2.png" and custom_sig_bytes is not None:
                zout.writestr(item, custom_sig_bytes)
            else:
                zout.writestr(item, zin.read(fname))
    return out_buf.getvalue()


def _make_p(
    runs: List[RunSpec],
    sz: int = 24,
    num_id: Optional[int] = None,
    jc: Optional[str] = None,
    space_before: int = 40,
    space_after: int = 40,
    tab_stops: Optional[List[int]] = None,
    page_break_before: bool = False,
) -> etree._Element:
    p = etree.Element(_w("p"))
    pPr = etree.SubElement(p, _w("pPr"))
    if page_break_before:
        etree.SubElement(pPr, _w("pageBreakBefore"))
    if num_id is not None:
        numPr = etree.SubElement(pPr, _w("numPr"))
        ilvl = etree.SubElement(numPr, _w("ilvl"))
        ilvl.set(_w("val"), "0")
        nid = etree.SubElement(numPr, _w("numId"))
        nid.set(_w("val"), str(num_id))
        ind = etree.SubElement(pPr, _w("ind"))
        if num_id == 2:
            ind.set(_w("left"), "360")
            ind.set(_w("hanging"), "360")
        else:
            ind.set(_w("left"), "284")
            ind.set(_w("hanging"), "218")
    if tab_stops:
        tabs = etree.SubElement(pPr, _w("tabs"))
        for pos in tab_stops:
            tb = etree.SubElement(tabs, _w("tab"))
            tb.set(_w("val"), "left")
            tb.set(_w("pos"), str(pos))
    sp = etree.SubElement(pPr, _w("spacing"))
    sp.set(_w("before"), str(space_before))
    sp.set(_w("after"), str(space_after))
    if jc:
        jc_el = etree.SubElement(pPr, _w("jc"))
        jc_el.set(_w("val"), jc)
    set_p_runs(p, runs, sz=sz)
    return p


def _make_bordered_table(
    col_widths: List[int],
    rows_spec: List[List[Tuple[List[RunSpec], int, Optional[str]]]],
    sz: int = 22,
    left_align_cols: Optional[set] = None,
) -> etree._Element:
    left_align_cols = left_align_cols or set()
    tbl = etree.Element(_w("tbl"))
    tblPr = etree.SubElement(tbl, _w("tblPr"))
    tblW = etree.SubElement(tblPr, _w("tblW"))
    tblW.set(_w("w"), str(sum(col_widths)))
    tblW.set(_w("type"), "dxa")
    jc = etree.SubElement(tblPr, _w("jc"))
    jc.set(_w("val"), "center")

    bdrs = etree.SubElement(tblPr, _w("tblBorders"))
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b = etree.SubElement(bdrs, _w(side))
        b.set(_w("val"), "single")
        b.set(_w("sz"), "4")
        b.set(_w("space"), "0")
        b.set(_w("color"), "auto")

    grid = etree.SubElement(tbl, _w("tblGrid"))
    for cw in col_widths:
        gc = etree.SubElement(grid, _w("gridCol"))
        gc.set(_w("w"), str(cw))

    for row in rows_spec:
        tr = etree.SubElement(tbl, _w("tr"))
        col_cursor = 0
        for runs, span, vmerge in row:
            tc = etree.SubElement(tr, _w("tc"))
            tcPr = etree.SubElement(tc, _w("tcPr"))
            start_col = col_cursor
            w_sum = sum(col_widths[col_cursor : col_cursor + span])
            col_cursor += span
            tcW = etree.SubElement(tcPr, _w("tcW"))
            tcW.set(_w("w"), str(w_sum))
            tcW.set(_w("type"), "dxa")
            if span > 1:
                gs = etree.SubElement(tcPr, _w("gridSpan"))
                gs.set(_w("val"), str(span))
            if vmerge is not None:
                vm = etree.SubElement(tcPr, _w("vMerge"))
                if vmerge == "restart":
                    vm.set(_w("val"), "restart")
            va = etree.SubElement(tcPr, _w("vAlign"))
            va.set(_w("val"), "center")

            p = etree.SubElement(tc, _w("p"))
            pPr = etree.SubElement(p, _w("pPr"))
            sp = etree.SubElement(pPr, _w("spacing"))
            sp.set(_w("before"), "30")
            sp.set(_w("after"), "30")
            pjc = etree.SubElement(pPr, _w("jc"))
            pjc.set(_w("val"), "left" if start_col in left_align_cols else "center")
            if vmerge != "continue":
                set_p_runs(p, runs, sz=sz)
    return tbl


def _build_footer_with_page_num(footer_bytes: bytes) -> bytes:
    ftr = etree.fromstring(footer_bytes)
    p = etree.SubElement(ftr, _w("p"))
    pPr = etree.SubElement(p, _w("pPr"))
    jc = etree.SubElement(pPr, _w("jc"))
    jc.set(_w("val"), "center")
    sp = etree.SubElement(pPr, _w("spacing"))
    sp.set(_w("before"), "20")
    sp.set(_w("after"), "0")

    p.append(_make_run("Trang ", bold=False, sz=18))
    fld_page = etree.SubElement(p, _w("fldSimple"))
    fld_page.set(_w("instr"), " PAGE ")
    fld_page.append(_make_run("1", bold=False, sz=18))
    p.append(_make_run("/", bold=False, sz=18))
    fld_num = etree.SubElement(p, _w("fldSimple"))
    fld_num.set(_w("instr"), " NUMPAGES ")
    fld_num.append(_make_run("2", bold=False, sz=18))

    return etree.tostring(ftr, xml_declaration=True, encoding="UTF-8", standalone="yes")


def _format_temp_runs(prefix: str, temp_val: str) -> List[RunSpec]:
    """Render temperature nicely with superscript degree symbol if written like 34oC / 340C / 34°C."""
    t = (temp_val or "").strip()
    if not t:
        return [(prefix, False)]
    cleaned = t.replace("⁰C", "").replace("°C", "").replace("oC", "").replace("0C", "").strip()
    if cleaned and cleaned.replace(",", ".").replace(".", "", 1).isdigit():
        return [(prefix + cleaned, False), ("0", False, "superscript"), ("C", False)]
    return [(prefix + t, False)]


# =========================================================================
# 1 & 2. MCCB and ACB Generator
# =========================================================================
def _generate_mccb_or_acb(req: ReportDocumentRequest, is_acb: bool = False) -> bytes:
    tpl = os.path.join(TEMPLATES_DIR, "mccb.docx")
    d = _read_data(MccbData, req.data)
    c = req.common

    with zipfile.ZipFile(tpl, "r") as z:
        root = etree.fromstring(z.read("word/document.xml"))
    body = root.find("w:body", NS)

    req_copy = req.model_copy(deep=True)
    if is_acb and (not c.loai_tieu_de or c.loai_tieu_de == "BIÊN BẢN KIỂM ĐỊNH"):
        req_copy.common.loai_tieu_de = "BIÊN BẢN THỬ NGHIỆM"
    update_header_table(body[0], req_copy, "BIÊN BẢN THỬ NGHIỆM" if is_acb else "BIÊN BẢN KIỂM ĐỊNH")

    equip_title = "MÁY CẮT HẠ THẾ (ACB)" if is_acb else "MÁY CẮT HẠ THẾ (MCCB)"
    verb = "thử nghiệm" if is_acb else "kiểm định"
    verb_upper = "THỬ NGHIỆM" if is_acb else "KIỂM ĐỊNH"

    set_p_runs(body[1], [(equip_title, True)], sz=38)
    set_p_runs(body[2], [("THÔNG TIN CÔNG TRÌNH", True)], sz=24)
    set_p_runs(body[3], [(f"Tên công trình: {c.ten_cong_trinh}", False)], sz=24)
    set_p_runs(body[4], [(f"Địa chỉ: {c.dia_chi}", False)], sz=24)
    set_p_runs(body[5], [(f"Chỉ danh: {c.chi_danh}", False)], sz=24)
    set_p_runs(body[6], [(f"Đơn vị yêu cầu: {c.don_vi_yeu_cau}", False)], sz=24)
    set_p_runs(body[7], [(f"Lý do {verb}: {c.ly_do}", False)], sz=24)
    set_p_runs(body[8], [(f"Nơi {verb}: {c.noi_kiem_dinh}", False)], sz=24)
    set_p_runs(body[9], [(f"Ngày {verb}: {c.ngay_kiem_dinh}", False)], sz=24)

    set_p_runs(body[10], [("THÔNG SỐ THIẾT BỊ", True)], sz=24)
    set_p_runs(body[11], [(f"Hiệu: {d.hieu}\t- Số cực: {d.so_cuc}", False)], sz=24)
    set_p_runs(body[12], [(f"Loại: {d.loai}\t- Kiểu: {d.kieu}", False)], sz=24)
    set_p_runs(body[13], [(f"Điện áp định mức: {d.dien_ap_dinh_muc}\t- Dòng điện định mức: {d.dong_dien_dinh_muc}", False)], sz=24)
    set_p_runs(body[14], [(f"Dòng điện ngắn mạch tối đa: {d.dong_ngan_mach}\t- Tần số: {d.tan_so}", False)], sz=24)
    set_p_runs(body[15], [(f"Điện áp cách điện định mức: {d.dien_ap_cach_dien}\t- Điện áp chịu xung định mức: {d.dien_ap_xung}", False)], sz=24)

    set_p_runs(body[16], [(f"KẾT QUẢ {verb_upper}", True)], sz=24)
    set_p_runs(body[17], [(f"Kiểm tra bên ngoài: {d.kiem_tra_ben_ngoai}\t- Số lượng: {d.so_luong}", False)], sz=24)
    set_p_runs(body[18], [("Kết quả thí nghiệm:" if is_acb else "Kết quả thử nghiệm:", False)], sz=24)

    row_vals = [
        [r.stt, r.rcd_close, r.rcd_open, r.rtx_a, r.rtx_b, r.rtx_c, r.utest, r.dong_cat, r.ket_qua, r.so_tem]
        for r in d.rows
    ]
    populate_dynamic_rows(body[19], header_row_count=2, row_values=row_vals, sz=24)

    set_p_runs(body[21], [(f"THIẾT BỊ {verb_upper}: ", True), (d.thiet_bi_kiem_dinh, False)], sz=24)
    set_p_runs(body[22], [(f"TIÊU CHUẨN {verb_upper}:", True)], sz=24)
    set_p_runs(body[23], [(d.tieu_chuan_kiem_dinh, False)], sz=24)
    set_p_runs(body[24], [(f"KẾT LUẬN: {d.ket_luan}", True)], sz=24)

    update_table_signature(body[25], req)
    return _repack_docx(tpl, root, _decode_custom_signature(req.signatory.custom_signature_data_url))


# =========================================================================
# 3. LA Generator
# =========================================================================
def _generate_la(req: ReportDocumentRequest) -> bytes:
    tpl = os.path.join(TEMPLATES_DIR, "la.docx")
    d = _read_data(LaData, req.data)
    c = req.common

    with zipfile.ZipFile(tpl, "r") as z:
        root = etree.fromstring(z.read("word/document.xml"))
    body = root.find("w:body", NS)

    update_header_table(body[0], req, "BIÊN BẢN KIỂM ĐỊNH")
    set_p_runs(body[1], [("CHỐNG SÉT VAN (LA)", True)], sz=36)
    set_p_runs(body[2], [("THÔNG TIN CÔNG TRÌNH", True)], sz=24)
    set_p_runs(body[3], [(f"Tên công trình: {c.ten_cong_trinh}", False)], sz=24)
    set_p_runs(body[4], [(f"Địa chỉ: {c.dia_chi}", False)], sz=24)
    set_p_runs(body[5], [(f"Chỉ danh: {c.chi_danh}", False)], sz=24)
    set_p_runs(body[6], [(f"Đơn vị yêu cầu: {c.don_vi_yeu_cau}", False)], sz=24)
    set_p_runs(body[7], [(f"Lý do kiểm định: {c.ly_do}", False)], sz=24)
    set_p_runs(body[8], [(f"Nơi kiểm định: {c.noi_kiem_dinh}", False)], sz=24)
    set_p_runs(body[9], [(f"Ngày kiểm định: {c.ngay_kiem_dinh}", False)], sz=24)

    set_p_runs(body[10], [("THÔNG SỐ THIẾT BỊ", True)], sz=24)
    set_p_runs(body[11], [(f"Vật liệu cách điện: {d.vat_lieu_cach_dien}\t- MCOV: {d.mcov}", False)], sz=24)
    set_p_runs(body[12], [(f"Điện áp định mức: {d.dien_ap_dinh_muc}\t- Tần số: {d.tan_so}", False)], sz=24)
    set_p_runs(body[13], [(f"Dòng điện xả tối đa: {d.dong_dien_xa}", False)], sz=24)

    set_p_runs(body[14], [("KẾT QUẢ KIỂM ĐỊNH", True)], sz=24)
    set_p_runs(body[15], [(f"Kiểm tra bên ngoài: {d.kiem_tra_ben_ngoai}\t- Số lượng: {d.so_luong}", False)], sz=24)
    set_p_runs(body[16], [("Kết quả kiểm định:", False)], sz=24)

    row_vals = [[r.doi_tuong_do, r.dien_tro_cach_dien, r.dong_dien_ro, r.dien_ap_ac] for r in d.rows]
    populate_dynamic_rows(body[17], header_row_count=1, row_values=row_vals, sz=24)

    set_p_runs(body[18], [("TIÊU CHUẨN KIỂM ĐỊNH: ", True), (d.tieu_chuan_kiem_dinh, False)], sz=24)
    set_p_runs(body[19], [("THIẾT BỊ KIỂM ĐỊNH: ", True), (d.thiet_bi_kiem_dinh, True)], sz=24)
    set_p_runs(body[20], [(f"KẾT LUẬN: {d.ket_luan}", True)], sz=24)

    update_paragraph_signature(body[21], body[24], req)
    return _repack_docx(tpl, root, _decode_custom_signature(req.signatory.custom_signature_data_url))


# =========================================================================
# 4 & 5. FCO and LBFCO Generator
# =========================================================================
def _generate_fco_or_lbfco(req: ReportDocumentRequest, is_lbfco: bool = False) -> bytes:
    tpl = os.path.join(TEMPLATES_DIR, "fco.docx")
    d = _read_data(FcoData, req.data)
    c = req.common

    with zipfile.ZipFile(tpl, "r") as z:
        root = etree.fromstring(z.read("word/document.xml"))
    body = root.find("w:body", NS)

    update_header_table(body[0], req, "BIÊN BẢN KIỂM ĐỊNH")
    title = "CẦU CHÌ TỰ RƠI CÓ DẬP HỒ QUANG (LBFCO)" if is_lbfco else "CẦU CHÌ TỰ RƠI (FCO)"
    title_sz = 30 if is_lbfco else 36
    set_p_runs(body[1], [(title, True)], sz=title_sz)
    set_p_runs(body[2], [("THÔNG TIN CÔNG TRÌNH", True)], sz=24)
    set_p_runs(body[3], [(f"Tên công trình: {c.ten_cong_trinh}", False)], sz=24)
    set_p_runs(body[4], [(f"Địa chỉ: {c.dia_chi}", False)], sz=24)
    set_p_runs(body[5], [(f"Chỉ danh: {c.chi_danh}", False)], sz=24)
    set_p_runs(body[6], [(f"Đơn vị yêu cầu: {c.don_vi_yeu_cau}", False)], sz=24)
    set_p_runs(body[7], [(f"Lý do kiểm định: {c.ly_do}", False)], sz=24)
    set_p_runs(body[8], [(f"Nơi kiểm định: {c.noi_kiem_dinh}", False)], sz=24)
    set_p_runs(body[9], [(f"Ngày kiểm định: {c.ngay_kiem_dinh}", False)], sz=24)

    set_p_runs(body[10], [("THÔNG SỐ THIẾT BỊ", True)], sz=24)
    set_p_runs(body[11], [(f"Vật liệu cách điện: {d.vat_lieu_cach_dien}\t- Dòng điện định mức: {d.dong_dien_dinh_muc}", False)], sz=24)
    set_p_runs(body[12], [(f"Điện áp định mức: {d.dien_ap_dinh_muc}\t- Khả năng cắt ngắn mạch: {d.kha_nang_cat_ngan_mach}", False)], sz=24)

    set_p_runs(body[13], [("KẾT QUẢ KIỂM ĐỊNH", True)], sz=24)
    set_p_runs(body[14], [(f"Kiểm tra bên ngoài: {d.kiem_tra_ben_ngoai}\t- Số lượng: {d.so_luong}", False)], sz=24)
    set_p_runs(body[15], [("Kết quả kiểm định:", False)], sz=24)

    row_vals = [
        [r.thiet_bi, r.rcd_truoc, r.rcd_sau, r.ac_kho, r.ac_uot, r.dong_cat, r.ket_qua]
        for r in d.rows
    ]
    populate_dynamic_rows(body[16], header_row_count=2, row_values=row_vals, sz=24)

    set_p_runs(body[17], [("TIÊU CHUẨN KIỂM ĐỊNH: ", True), (d.tieu_chuan_kiem_dinh, False)], sz=24)
    set_p_runs(body[18], [("THIẾT BỊ KIỂM ĐỊNH: ", True), (d.thiet_bi_kiem_dinh, True)], sz=24)
    set_p_runs(body[19], [(f"KẾT LUẬN: {d.ket_luan}", True)], sz=24)

    update_paragraph_signature(body[20], body[23], req)
    return _repack_docx(tpl, root, _decode_custom_signature(req.signatory.custom_signature_data_url))


# =========================================================================
# 6. Điện trở nối đất (ĐTNĐ) Generator
# =========================================================================
def _generate_dtnd(req: ReportDocumentRequest) -> bytes:
    tpl = os.path.join(TEMPLATES_DIR, "dtnd.docx")
    d = _read_data(DtndData, req.data)
    c = req.common

    with zipfile.ZipFile(tpl, "r") as z:
        root = etree.fromstring(z.read("word/document.xml"))
    body = root.find("w:body", NS)

    loai_td = c.loai_tieu_de if c.loai_tieu_de and c.loai_tieu_de != "BIÊN BẢN KIỂM ĐỊNH" else "BIÊN BẢN THỬ NGHIỆM"
    req_copy = req.model_copy(deep=True)
    req_copy.common.loai_tieu_de = loai_td
    update_header_table(body[0], req_copy, "BIÊN BẢN THỬ NGHIỆM")

    set_p_runs(body[1], [("ĐIỆN TRỞ NỐI ĐẤT", True)], sz=36)
    set_p_runs(body[2], [("THÔNG TIN CÔNG TRÌNH", True)], sz=24)
    set_p_runs(body[3], [(f"Tên công trình: {c.ten_cong_trinh}", False)], sz=24)
    set_p_runs(body[4], [(f"Địa chỉ: {c.dia_chi}", False)], sz=24)
    set_p_runs(body[6], [(f"Chỉ danh: {c.chi_danh}", False)], sz=24)
    set_p_runs(body[7], [(f"Đơn vị yêu cầu: {c.don_vi_yeu_cau}", False)], sz=24)
    set_p_runs(body[8], [(f"Lý do thử nghiệm: {c.ly_do}", False)], sz=24)
    set_p_runs(body[9], [(f"Nơi thử nghiệm: {c.noi_kiem_dinh}", False)], sz=24)
    set_p_runs(body[10], [(f"Ngày thử nghiệm: {c.ngay_kiem_dinh}", False)], sz=24)

    set_p_runs(body[11], [("KẾT QUẢ THỬ NGHIỆM", True)], sz=24)

    row_vals = [[r.stt, r.chi_danh, r.ket_noi_trung_tinh, r.loai_tiep_dat, r.gia_tri_do] for r in d.rows]
    populate_dynamic_rows(body[12], header_row_count=1, row_values=row_vals, sz=24)

    set_p_runs(body[13], [("THIẾT BỊ THỬ NGHIỆM", True), (f": {d.thiet_bi_thu_nghiem}", False)], sz=24)
    set_p_runs(body[14], [("GHI CHÚ:", True)], sz=24)
    set_p_runs(body[15], [(d.ghi_chu_1, False)], sz=24)
    set_p_runs(body[16], [(d.ghi_chu_2, False)], sz=24)

    update_table_signature(body[18], req)
    return _repack_docx(tpl, root, _decode_custom_signature(req.signatory.custom_signature_data_url))


# =========================================================================
# 7. Máy biến áp 1 pha (MBA 1P) Generator
# =========================================================================
def _generate_mba_1p(req: ReportDocumentRequest) -> bytes:
    tpl = os.path.join(TEMPLATES_DIR, "mba_1p_shell.docx")
    d = _read_data(Mba1PData, req.data)
    c = req.common

    with zipfile.ZipFile(tpl, "r") as z:
        root = etree.fromstring(z.read("word/document.xml"))
        footer1_bytes = z.read("word/footer1.xml")

    body = root.find("w:body", NS)
    header_tbl = copy.deepcopy(body[0])
    sig_tbl = copy.deepcopy(body[25])
    sectPr = copy.deepcopy(body[-1])
    for ch in list(body):
        body.remove(ch)

    update_header_table(header_tbl, req, "BIÊN BẢN KIỂM ĐỊNH")
    update_table_signature(sig_tbl, req)

    body.append(header_tbl)
    body.append(_make_p([("MÁY BIẾN ÁP 1 PHA", True)], sz=34, jc="center", space_before=120, space_after=80))

    body.append(
        _make_p(
            [("LÝ LỊCH THIẾT BỊ", True), (f"\t- Số tem: {d.so_tem}", False)],
            sz=23,
            num_id=2,
            tab_stops=[6379],
            space_before=30,
            space_after=30,
        )
    )
    body.append(_make_p([(f"Hiệu máy: {d.hieu_may}\t- Số máy: {d.so_may}", False)], sz=23, num_id=3, tab_stops=[6379]))
    body.append(_make_p([(f"Nước sản xuất: {d.nuoc_san_xuat}\t- Năm sản xuất: {d.nam_san_xuat}", False)], sz=23, num_id=3, tab_stops=[6379]))
    body.append(_make_p([(f"Tên công trình: {c.ten_cong_trinh}", False)], sz=23, num_id=3))
    body.append(_make_p([(f"Địa chỉ: {c.dia_chi}", False)], sz=23, num_id=3))
    body.append(_make_p([(f"Đơn vị yêu cầu: {c.don_vi_yeu_cau}", False)], sz=23, num_id=3))
    body.append(_make_p([(f"Lý do kiểm định: {c.ly_do}", False)], sz=23, num_id=3))
    body.append(_make_p([(f"Nơi kiểm định: {c.noi_kiem_dinh}", False)], sz=23, num_id=3))
    body.append(_make_p([(f"Ngày kiểm định: {c.ngay_kiem_dinh}", False)], sz=23, num_id=3))

    body.append(_make_p([("QUY CÁCH KỸ THUẬT", True)], sz=23, num_id=2, space_before=40, space_after=30))
    body.append(
        _make_p(
            [(f"Công suất định mức: {d.cong_suat_dinh_muc}\t- Số pha: {d.so_pha}\t- Tần số: {d.tan_so}", False)],
            sz=23,
            num_id=3,
            tab_stops=[4800, 7600],
        )
    )
    body.append(_make_p([(f"Điện áp định mức: {d.dien_ap_dinh_muc}\t- Tổ đấu dây: {d.to_dau_day}", False)], sz=23, num_id=3, tab_stops=[4800]))

    body.append(_make_p([("KẾT QUẢ KIỂM ĐỊNH", True)], sz=23, num_id=2, space_before=40, space_after=30))
    body.append(_make_p([(f"Kiểm tra bên ngoài: {d.kiem_tra_ben_ngoai}", False)], sz=23, num_id=4))
    body.append(_make_p([("Điện trở cách điện: (MΩ)", False)], sz=23, num_id=4))

    ins_rows = [
        [
            ([("Đối tượng đo", True)], 1, None),
            ([("R", True), ("60’’", True, "subscript"), (" (MΩ)", True)], 1, None),
            ([("R", True), ("15’’", True, "subscript"), (" (MΩ)", True)], 1, None),
            ([("K", True), ("ht", True, "subscript")], 1, None),
        ]
    ]
    for r in d.cach_dien_rows:
        ins_rows.append(
            [([(r.doi_tuong_do, False)], 1, None), ([(r.r60, False)], 1, None), ([(r.r15, False)], 1, None), ([(r.kht, False)], 1, None)]
        )
    body.append(_make_bordered_table([2600, 2200, 2200, 2000], ins_rows, sz=22))

    body.append(_make_p([("Điện trở một chiều cuộn dây:", False)], sz=23, num_id=4, space_before=50, space_after=30))
    n_taps = max(len(d.dien_tro_cao_ap), 1)
    tap_w = 5400 // n_taps
    dc_widths = [1600] + [tap_w] * n_taps + [1200, 1200]
    dc_rows = [
        [([("", True)], 1, None), ([("Cuộn dây cao áp (Ω)", True)], n_taps, None), ([("Cuộn dây hạ áp (mΩ)", True)], 2, None)],
        [([("Nấc", False)], 1, None)] + [([(str(i + 1), False)], 1, None) for i in range(n_taps)] + [([("HA 1", False)], 1, None), ([("HA 2", False)], 1, None)],
        [([("Kết quả đo", False)], 1, None)]
        + [([((d.dien_tro_cao_ap[i] if i < len(d.dien_tro_cao_ap) else ""), False)], 1, None) for i in range(n_taps)]
        + [([(d.dien_tro_ha_1, False)], 1, None), ([(d.dien_tro_ha_2, False)], 1, None)],
    ]
    body.append(_make_bordered_table(dc_widths, dc_rows, sz=22))

    body.append(_make_p([("Tỉ số biến áp:", False)], sz=23, num_id=4, space_before=50, space_after=30))
    n_h1 = max(len(d.ti_so_ha_1), 1)
    n_h2 = max(len(d.ti_so_ha_2), 1)
    ratio_cell_w = 8400 // (n_h1 + n_h2)
    ratio_widths = [1400] + [ratio_cell_w] * (n_h1 + n_h2)
    ratio_rows = [
        [([("Cao", True)], 1, None), ([("Hạ 1", True)], n_h1, None), ([("Hạ 2", True)], n_h2, None)],
        [([("Nấc", False)], 1, None)] + [([(str(i + 1), False)], 1, None) for i in range(n_h1)] + [([(str(i + 1), False)], 1, None) for i in range(n_h2)],
        [([("Kết quả đo", False)], 1, None)]
        + [([((d.ti_so_ha_1[i] if i < len(d.ti_so_ha_1) else ""), False)], 1, None) for i in range(n_h1)]
        + [([((d.ti_so_ha_2[i] if i < len(d.ti_so_ha_2) else ""), False)], 1, None) for i in range(n_h2)],
    ]
    body.append(_make_bordered_table(ratio_widths, ratio_rows, sz=21))

    body.append(_make_p([("Thí nghiệm không tải:", False)], sz=23, num_id=4, space_before=50, space_after=30))
    noload_rows = [
        [
            ([("Đối tượng đo", True)], 1, None),
            ([("U", True), ("0", True, "subscript"), ("(V)", True)], 1, None),
            ([("I", True), ("0", True, "subscript"), (" (A)", True)], 1, None),
            ([("I", True), ("0", True, "subscript"), ("%", True)], 1, None),
            ([("P", True), ("0", True, "subscript"), ("(W)", True)], 1, None),
        ],
        [
            ([("Kết quả đo", False)], 1, None),
            ([(d.khong_tai_u0, False)], 1, None),
            ([(d.khong_tai_i0, False)], 1, None),
            ([(d.khong_tai_i0_pct, False)], 1, None),
            ([(d.khong_tai_p0, False)], 1, None),
        ],
    ]
    body.append(_make_bordered_table([2000, 1500, 1500, 1500, 1500], noload_rows, sz=22))

    body.append(_make_p([("Thí nghiệm ngắn mạch:", False)], sz=23, num_id=4, space_before=80, space_after=40, page_break_before=True))
    sc_rows = [
        [
            ([("Đối tượng đo", True)], 1, None),
            ([("U", True), ("N", True, "subscript"), (" (V)", True)], 1, None),
            ([("U", True), ("N", True, "subscript"), (" (%)", True)], 1, None),
            ([("I", True), ("N", True, "subscript")], 1, None),
            ([("P", True), ("N75", True, "subscript"), (" (W)", True)], 1, None),
        ],
        [
            ([("Kết quả đo", False)], 1, None),
            ([(d.ngan_mach_un, False)], 1, None),
            ([(d.ngan_mach_un_pct, False)], 1, None),
            ([(d.ngan_mach_in, False)], 1, None),
            ([(d.ngan_mach_pn75, False)], 1, None),
        ],
    ]
    body.append(_make_bordered_table([2000, 1500, 1500, 1500, 1500], sc_rows, sz=22))

    body.append(_make_p([("Thử điện áp tăng cao:", False)], sz=23, num_id=4, space_before=60, space_after=40))
    ac_rows = [[([("Đối tượng thử", True)], 1, None), ([("U", True), ("thử", True, "subscript"), (" (kV)", True)], 1, None), ([("Thời gian thử", True)], 1, None)]]
    for r in d.dien_ap_tang_cao_rows:
        ac_rows.append([([(r.doi_tuong_thu, False)], 1, None), ([(r.u_thu, False)], 1, None), ([(r.thoi_gian, False)], 1, None)])
    body.append(_make_bordered_table([2800, 1800, 2200], ac_rows, sz=22))

    body.append(_make_p([("THIẾT BỊ KIỂM ĐỊNH: ", True), (d.thiet_bi_kiem_dinh, False)], sz=24, num_id=2, space_before=100, space_after=60))
    body.append(_make_p([(f"KẾT LUẬN: {d.ket_luan}", True)], sz=24, num_id=2, space_before=60, space_after=120))
    body.append(sig_tbl)
    body.append(sectPr)

    return _repack_docx(
        tpl,
        root,
        _decode_custom_signature(req.signatory.custom_signature_data_url),
        extra_xml_overrides={"word/footer1.xml": _build_footer_with_page_num(footer1_bytes)},
    )


# =========================================================================
# 8. Máy biến áp 3 pha (MBA 3P) Generator (from 092 BB MBA 1500kVA.doc)
# =========================================================================
def _generate_mba_3p(req: ReportDocumentRequest) -> bytes:
    tpl = os.path.join(TEMPLATES_DIR, "mba_1p_shell.docx")
    d = _read_data(Mba3PData, req.data)
    c = req.common

    with zipfile.ZipFile(tpl, "r") as z:
        root = etree.fromstring(z.read("word/document.xml"))
        footer1_bytes = z.read("word/footer1.xml")

    body = root.find("w:body", NS)
    header_tbl = copy.deepcopy(body[0])
    sig_tbl = copy.deepcopy(body[25])
    sectPr = copy.deepcopy(body[-1])
    for ch in list(body):
        body.remove(ch)

    update_header_table(header_tbl, req, "BIÊN BẢN KIỂM ĐỊNH")
    update_table_signature(sig_tbl, req)

    body.append(header_tbl)
    body.append(_make_p([("MÁY BIẾN ÁP 3 PHA", True)], sz=34, jc="center", space_before=100, space_after=60))

    body.append(
        _make_p(
            [("LÝ LỊCH THIẾT BỊ", True), (f"\t- Số tem: {d.so_tem}", True)],
            sz=23,
            num_id=2,
            tab_stops=[6379],
            space_before=25,
            space_after=25,
        )
    )
    body.append(_make_p([(f"Hiệu máy: {d.hieu_may}\t- Số máy: {d.so_may}", False)], sz=23, num_id=3, tab_stops=[6379], space_before=25, space_after=25))
    body.append(_make_p([(f"Nước sản xuất: {d.nuoc_san_xuat}\t- Năm sản xuất: {d.nam_san_xuat}", False)], sz=23, num_id=3, tab_stops=[6379], space_before=25, space_after=25))
    body.append(_make_p([(f"Tên công trình: {c.ten_cong_trinh}", False)], sz=23, num_id=3, space_before=25, space_after=25))
    body.append(_make_p([(f"Địa chỉ: {c.dia_chi}", False)], sz=23, num_id=3, space_before=25, space_after=25))
    body.append(_make_p([(f"Đơn vị yêu cầu: {c.don_vi_yeu_cau}", False)], sz=23, num_id=3, space_before=25, space_after=25))
    body.append(_make_p([(f"Lý do kiểm định: {c.ly_do}", False)], sz=23, num_id=3, space_before=25, space_after=25))
    body.append(_make_p([(f"Nơi kiểm định: {c.noi_kiem_dinh}", False)], sz=23, num_id=3, space_before=25, space_after=25))
    body.append(_make_p([(f"Ngày kiểm định: {c.ngay_kiem_dinh}", False)], sz=23, num_id=3, space_before=25, space_after=25))

    body.append(_make_p([("QUY CÁCH KỸ THUẬT", True)], sz=23, num_id=2, space_before=35, space_after=25))
    body.append(
        _make_p(
            [(f"Công suất định mức: {d.cong_suat_dinh_muc}\t- Số pha: {d.so_pha}\t- Tần số: {d.tan_so}", False)],
            sz=23,
            num_id=3,
            tab_stops=[4400, 7200],
            space_before=25,
            space_after=25,
        )
    )
    body.append(
        _make_p(
            [(f"Điện áp định mức: {d.dien_ap_dinh_muc}\t- Tổ đấu dây: {d.to_dau_day}", False)],
            sz=23,
            num_id=3,
            tab_stops=[4400],
            space_before=25,
            space_after=25,
        )
    )

    body.append(_make_p([("KẾT QUẢ KIỂM ĐỊNH", True)], sz=23, num_id=2, space_before=35, space_after=25))
    body.append(_make_p([(f"Kiểm tra bên ngoài: {d.kiem_tra_ben_ngoai}", False)], sz=23, num_id=4, space_before=25, space_after=25))

    ins_heading_runs: List[RunSpec] = [("Điện trở cách điện: (MΩ)", True)] + _format_temp_runs("\t- Nhiệt độ: ", d.nhiet_do)
    body.append(_make_p(ins_heading_runs, sz=23, num_id=4, tab_stops=[5600], space_before=25, space_after=25))

    ins_rows = [
        [
            ([("Đối tượng đo", True)], 1, None),
            ([("R", True), ("60’’", True, "subscript"), ("(MΩ)", True)], 1, None),
            ([("R", True), ("15’’", True, "subscript"), ("(MΩ)", True)], 1, None),
            ([("K", True), ("ht", True, "subscript")], 1, None),
        ]
    ]
    for r in d.cach_dien_rows:
        ins_rows.append(
            [([(r.doi_tuong_do, False)], 1, None), ([(r.r60, False)], 1, None), ([(r.r15, False)], 1, None), ([(r.kht, False)], 1, None)]
        )
    body.append(_make_bordered_table([2400, 2200, 2200, 2000], ins_rows, sz=22))

    # 3. Điện trở một chiều cuộn dây (with vertically merged LV column!)
    body.append(_make_p([("Điện trở một chiều cuộn dây:", False)], sz=23, num_id=4, space_before=35, space_after=25))
    lv_text = "\n".join(x for x in [d.dc_ha_an, d.dc_ha_bn, d.dc_ha_cn] if x)
    dc_rows: List[List[Tuple[List[RunSpec], int, Optional[str]]]] = [
        [
            ([("", True)], 1, None),
            ([("Cuộn dây cao áp (Ω)", True)], 3, None),
            ([("Cuộn dây hạ áp (mΩ)", True)], 1, None),
        ],
        [
            ([("Nấc", False)], 1, None),
            ([("AB", False)], 1, None),
            ([("BC", False)], 1, None),
            ([("CA", False)], 1, None),
            ([(lv_text, False)], 1, "restart"),
        ],
    ]
    for r in d.dc_cao_ap_rows:
        dc_rows.append(
            [
                ([(r.nac, False)], 1, None),
                ([(r.ab, False)], 1, None),
                ([(r.bc, False)], 1, None),
                ([(r.ca, False)], 1, None),
                ([("", False)], 1, "continue"),
            ]
        )
    body.append(_make_bordered_table([1200, 1500, 1500, 1500, 2500], dc_rows, sz=22))

    # 4. Tỉ số biến áp
    body.append(_make_p([("Tỉ số biến áp:", False)], sz=23, num_id=4, space_before=35, space_after=25))
    ratio_rows = [
        [
            ([("Nấc", False)], 1, None),
            ([("K", False), ("1", False, "subscript")], 1, None),
            ([("K", False), ("2", False, "subscript")], 1, None),
            ([("K", False), ("3", False, "subscript")], 1, None),
        ]
    ]
    for r in d.ti_so_rows:
        ratio_rows.append(
            [([(r.nac, False)], 1, None), ([(r.k1, False)], 1, None), ([(r.k2, False)], 1, None), ([(r.k3, False)], 1, None)]
        )
    body.append(_make_bordered_table([1200, 1700, 1700, 1700], ratio_rows, sz=22))

    # --- PAGE 2 ---
    body.append(
        _make_p(
            [("Thử nghiệm không tải: Hở mạch cuộn cao áp, đưa điện áp vào cuộn hạ áp:", False)],
            sz=23,
            num_id=4,
            space_before=60,
            space_after=35,
            page_break_before=True,
        )
    )
    noload_rows = [
        [
            ([("Đối tượng đo", True)], 1, None),
            ([("U", True), ("0", True, "subscript"), ("(V)", True)], 1, None),
            ([("I", True), ("0", True, "subscript"), ("(A)", True)], 1, None),
            ([("I", True), ("0", True, "subscript"), ("%", True)], 1, None),
            ([("P", True), ("0", True, "subscript"), ("(W)", True)], 1, None),
        ],
        [
            ([("Kết quả đo", False)], 1, None),
            ([(d.khong_tai_u0, False)], 1, None),
            ([(d.khong_tai_i0, False)], 1, None),
            ([(d.khong_tai_i0_pct, False)], 1, None),
            ([(d.khong_tai_p0, False)], 1, None),
        ],
    ]
    body.append(_make_bordered_table([2000, 1500, 1500, 1500, 1700], noload_rows, sz=22))

    body.append(
        _make_p(
            [("Thử nghiệm ngắn mạch: Đấu tắt cuộn dây hạ áp, đưa điện áp vào phía cuộn dây cao áp", False)],
            sz=23,
            num_id=4,
            space_before=60,
            space_after=35,
        )
    )
    sc_rows = [
        [
            ([("Đối tượng đo", True)], 1, None),
            ([("U", True), ("N", True, "subscript"), ("(V)", True)], 1, None),
            ([("U", True), ("N", True, "subscript"), ("(%)", True)], 1, None),
            ([("I", True), ("N", True, "subscript"), ("(A)", True)], 1, None),
            ([("P", True), ("N75", True, "subscript"), ("(W)", True)], 1, None),
        ],
        [
            ([("Kết quả đo", False)], 1, None),
            ([(d.ngan_mach_un, False)], 1, None),
            ([(d.ngan_mach_un_pct, False)], 1, None),
            ([(d.ngan_mach_in, False)], 1, None),
            ([(d.ngan_mach_pn75, False)], 1, None),
        ],
    ]
    body.append(_make_bordered_table([2000, 1500, 1500, 1500, 1700], sc_rows, sz=22))

    body.append(_make_p([("Thử nghiệm điện áp tăng cao:", False)], sz=23, num_id=4, space_before=60, space_after=35))
    ac_rows = [
        [
            ([("Đối tượng thử", True)], 1, None),
            ([("U", True), ("thử", True, "subscript"), ("(kV)", True)], 1, None),
            ([("Thời gian thử", True)], 1, None),
        ]
    ]
    for r in d.dien_ap_tang_cao_rows:
        ac_rows.append([([(r.doi_tuong_thu, False)], 1, None), ([(r.u_thu, False)], 1, None), ([(r.thoi_gian, False)], 1, None)])
    body.append(_make_bordered_table([2800, 1800, 2200], ac_rows, sz=22))

    body.append(_make_p([("THIẾT BỊ KIỂM ĐỊNH: ", True), (d.thiet_bi_kiem_dinh, False)], sz=24, num_id=2, space_before=90, space_after=50))
    body.append(_make_p([(f"KẾT LUẬN: {d.ket_luan}", True)], sz=24, num_id=2, space_before=50, space_after=100))
    body.append(sig_tbl)
    body.append(sectPr)

    return _repack_docx(
        tpl,
        root,
        _decode_custom_signature(req.signatory.custom_signature_data_url),
        extra_xml_overrides={"word/footer1.xml": _build_footer_with_page_num(footer1_bytes)},
    )


# =========================================================================
# 9. Thông tuyến cáp ngầm trung thế (from 097 BB Thông tuyến cáp ngầm TT.doc)
# =========================================================================
def _generate_cap_ngam(req: ReportDocumentRequest) -> bytes:
    tpl = os.path.join(TEMPLATES_DIR, "mba_1p_shell.docx")
    d = _read_data(CapNgamData, req.data)
    c = req.common

    with zipfile.ZipFile(tpl, "r") as z:
        root = etree.fromstring(z.read("word/document.xml"))

    body = root.find("w:body", NS)
    header_tbl = copy.deepcopy(body[0])
    sig_tbl = copy.deepcopy(body[25])
    sectPr = copy.deepcopy(body[-1])
    for ch in list(body):
        body.remove(ch)

    update_header_table(header_tbl, req, "BIÊN BẢN KIỂM ĐỊNH")
    update_table_signature(sig_tbl, req)

    body.append(header_tbl)
    body.append(_make_p([("THÔNG TUYẾN CÁP NGẦM TRUNG THẾ", True)], sz=32, jc="center", space_before=100, space_after=70))

    body.append(_make_p([("THÔNG TIN CÔNG TRÌNH", True)], sz=24, num_id=2, space_before=30, space_after=30))
    body.append(_make_p([(f"Tên công trình: {c.ten_cong_trinh}", False)], sz=24, num_id=3, space_before=25, space_after=25))
    body.append(_make_p([(f"Địa chỉ: {c.dia_chi}", False)], sz=24, num_id=3, space_before=25, space_after=25))
    body.append(_make_p([(f"Chỉ danh: {c.chi_danh}", False)], sz=24, num_id=3, space_before=25, space_after=25))
    body.append(_make_p([(f"Đơn vị yêu cầu: {c.don_vi_yeu_cau}", False)], sz=24, num_id=3, space_before=25, space_after=25))
    body.append(_make_p([(f"Lý do kiểm định: {c.ly_do}", False)], sz=24, num_id=3, space_before=25, space_after=25))
    body.append(_make_p([(f"Nơi kiểm định: {c.noi_kiem_dinh}", False)], sz=24, num_id=3, space_before=25, space_after=25))
    body.append(_make_p([(f"Ngày kiểm định: {c.ngay_kiem_dinh}", False)], sz=24, num_id=3, space_before=25, space_after=25))

    body.append(
        _make_p(
            [("THÔNG SỐ THIẾT BỊ", True), (f"\t- Số tem: {d.so_tem}", True)],
            sz=24,
            num_id=2,
            tab_stops=[6200],
            space_before=40,
            space_after=25,
        )
    )
    body.append(
        _make_p(
            [(f"Đoạn cáp đi từ: {d.doan_cap_tu}\t- Đến: {d.doan_cap_den}", False)],
            sz=24,
            num_id=3,
            tab_stops=[6200],
            space_before=25,
            space_after=25,
        )
    )
    # Render mm2 with superscript 2 if applicable
    td_str = (d.tiet_dien or "").strip()
    if td_str.endswith("mm2"):
        td_runs: List[RunSpec] = [(f"Loại cáp: {d.loai_cap}\t- Tiết diện: {td_str[:-1]}", False), ("2", False, "superscript")]
    else:
        td_runs = [(f"Loại cáp: {d.loai_cap}\t- Tiết diện: {td_str}", False)]
    body.append(_make_p(td_runs, sz=24, num_id=3, tab_stops=[6200], space_before=25, space_after=25))
    body.append(
        _make_p(
            [(f"Điện áp định mức: {d.dien_ap_dinh_muc}\t- Tần số: {d.tan_so}", False)],
            sz=24,
            num_id=3,
            tab_stops=[6200],
            space_before=25,
            space_after=25,
        )
    )

    body.append(_make_p([("KẾT QUẢ KIỂM ĐỊNH", True)], sz=24, num_id=2, space_before=40, space_after=25))
    body.append(_make_p([(f"Kiểm tra bên ngoài: {d.kiem_tra_ben_ngoai}", False)], sz=24, num_id=4, space_before=25, space_after=25))
    ins_p_runs: List[RunSpec] = [("Điện trở cách điện:", False)] + _format_temp_runs("\tNhiệt độ: ", d.nhiet_do)
    body.append(_make_p(ins_p_runs, sz=24, num_id=4, tab_stops=[6200], space_before=25, space_after=25))

    ins_tbl_rows = [[([("Đối tượng đo", True)], 1, None), ([("Tiêu chuẩn (MΩ)", True)], 1, None), ([("Số liệu đo (MΩ)", True)], 1, None)]]
    for r in d.cach_dien_rows:
        ins_tbl_rows.append([([(r.doi_tuong_do, False)], 1, None), ([(r.tieu_chuan, False)], 1, None), ([(r.so_lieu_do, False)], 1, None)])
    body.append(_make_bordered_table([2800, 2600, 2800], ins_tbl_rows, sz=23))

    body.append(_make_p([("Điện áp một chiều tăng cao:", False)], sz=24, num_id=4, space_before=35, space_after=25))
    dc_tbl_rows = [
        [
            ([("Đối tượng đo", True)], 1, None),
            ([("Thời gian (phút)", True)], 1, None),
            ([("Điện áp thử nghiệm (kV)", True)], 1, None),
            ([("Dòng rò (µA)", True)], 1, None),
        ]
    ]
    for r in d.dc_tang_cao_rows:
        dc_tbl_rows.append(
            [
                ([(r.doi_tuong_do, False)], 1, None),
                ([(r.thoi_gian, False)], 1, None),
                ([(r.dien_ap_thu, False)], 1, None),
                ([(r.dong_ro, False)], 1, None),
            ]
        )
    body.append(_make_bordered_table([2400, 2200, 2800, 2000], dc_tbl_rows, sz=23))

    body.append(_make_p([("THIẾT BỊ KIỂM ĐỊNH: ", True), (d.thiet_bi_kiem_dinh, False)], sz=24, num_id=2, space_before=45, space_after=30))
    body.append(_make_p([(f"KẾT LUẬN: {d.ket_luan}", True)], sz=24, num_id=2, space_before=30, space_after=60))
    body.append(sig_tbl)
    body.append(sectPr)

    return _repack_docx(tpl, root, _decode_custom_signature(req.signatory.custom_signature_data_url))


# =========================================================================
# 10. Tủ tụ bù hạ thế (from 109 BB Tụ Bù.docx)
# =========================================================================
def _generate_tu_bu(req: ReportDocumentRequest) -> bytes:
    tpl = os.path.join(TEMPLATES_DIR, "tu_bu.docx")
    d = _read_data(TuBuData, req.data)
    c = req.common

    with zipfile.ZipFile(tpl, "r") as z:
        root = etree.fromstring(z.read("word/document.xml"))
    body = root.find("w:body", NS)

    update_header_table(body[0], req, "BIÊN BẢN KIỂM ĐỊNH")
    set_p_runs(body[1], [("TỦ TỤ BÙ HẠ THẾ", True)], sz=36)
    set_p_runs(body[2], [("THÔNG TIN CÔNG TRÌNH", True)], sz=24)
    set_p_runs(body[3], [(f"Tên công trình: {c.ten_cong_trinh}", False)], sz=24)
    set_p_runs(body[4], [(f"Địa chỉ: {c.dia_chi}", False)], sz=24)
    set_p_runs(body[5], [(f"Chỉ danh: {c.chi_danh}", False)], sz=24)
    set_p_runs(body[6], [(f"Đơn vị yêu cầu: {c.don_vi_yeu_cau}", False)], sz=24)
    set_p_runs(body[7], [(f"Lý do kiểm định: {c.ly_do}", False)], sz=24)
    set_p_runs(body[8], [(f"Nơi kiểm định: {c.noi_kiem_dinh}", False)], sz=24)
    set_p_runs(body[9], [(f"Ngày kiểm định: {c.ngay_kiem_dinh}", False)], sz=24)

    set_p_runs(body[10], [("KẾT QUẢ KIỂM ĐỊNH", True)], sz=24)
    set_p_runs(body[11], [(f"Kiểm tra bên ngoài: {d.kiem_tra_ben_ngoai}", False)], sz=24)
    set_p_runs(body[12], [("Kết quả thử nghiệm MCCB:", False)], sz=24)

    set_p_runs(body[13], [(f"MCCB: {d.mccb_tong_thong_so}\t- Số lượng: {d.mccb_tong_so_luong}", False)], sz=24)
    tong_vals = [
        [r.stt, r.rcd_close, r.rcd_open, r.rtx_a, r.rtx_b, r.rtx_c, r.utest, r.dong_cat, r.ket_qua]
        for r in d.mccb_tong_rows
    ]
    populate_dynamic_rows(body[14], header_row_count=2, row_values=tong_vals, sz=24)

    set_p_runs(body[15], [(f"MCCB: {d.mccb_nhanh_thong_so}\t- Số lượng: {d.mccb_nhanh_so_luong}", False)], sz=24)
    nhanh_vals = [
        [r.stt, r.rcd_close, r.rcd_open, r.rtx_a, r.rtx_b, r.rtx_c, r.utest, r.dong_cat, r.ket_qua]
        for r in d.mccb_nhanh_rows
    ]
    populate_dynamic_rows(body[16], header_row_count=2, row_values=nhanh_vals, sz=24)

    set_p_runs(body[19], [("Kết quả thử nghiệm Contactor", False)], sz=24)
    set_p_runs(body[20], [(f"Contactor: {d.contactor_thong_so}\t- Số lượng: {d.contactor_so_luong}", False)], sz=24)
    cont_vals = [
        [r.stt, r.rcd_close, r.rcd_open, r.rtx_a, r.rtx_b, r.rtx_c, r.utest, r.dong_cat, r.ket_qua]
        for r in d.contactor_rows
    ]
    populate_dynamic_rows(body[21], header_row_count=2, row_values=cont_vals, sz=24)

    set_p_runs(body[22], [(f"Kết quả thử nghiệm tụ bù:\tSố lượng: {d.tu_bu_so_luong}", False)], sz=24)
    cap_vals = [[r.stt, r.dung_luong, r.r_cach_dien, r.dien_dung, r.ket_qua] for r in d.tu_bu_rows]
    populate_dynamic_rows(body[23], header_row_count=1, row_values=cap_vals, sz=24, vmerge_col=1)

    set_p_runs(body[24], [("THIẾT BỊ KIỂM ĐỊNH: ", True), (d.thiet_bi_kiem_dinh, False)], sz=24)
    set_p_runs(body[25], [("TIÊU CHUẨN KIỂM ĐỊNH:  ", True), (d.tieu_chuan_kiem_dinh, False)], sz=24)
    set_p_runs(body[26], [(f"KẾT LUẬN: {d.ket_luan}", True)], sz=24)

    update_paragraph_signature(body[27], body[30], req)
    return _repack_docx(tpl, root, _decode_custom_signature(req.signatory.custom_signature_data_url))


def generate_report_docx(req: ReportDocumentRequest) -> bytes:
    generators = {
        "mba_1p": _generate_mba_1p,
        "mba_3p": _generate_mba_3p,
        "mccb": lambda r: _generate_mccb_or_acb(r, is_acb=False),
        "acb": lambda r: _generate_mccb_or_acb(r, is_acb=True),
        "la": _generate_la,
        "fco": lambda r: _generate_fco_or_lbfco(r, is_lbfco=False),
        "lbfco": lambda r: _generate_fco_or_lbfco(r, is_lbfco=True),
        "dtnd": _generate_dtnd,
        "cap_ngam": _generate_cap_ngam,
        "tu_bu": _generate_tu_bu,
    }
    if req.report_type not in generators:
        raise ValueError(f"Unsupported report_type: {req.report_type}")
    return generators[req.report_type](req)
