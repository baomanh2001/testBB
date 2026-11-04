import base64
import copy
import io
import os
import zipfile
from typing import Dict, List, Optional, Tuple, Union
from lxml import etree

from app.schemas import (
    DtndData,
    FcoData,
    LaData,
    Mba1PData,
    MccbData,
    ReportDocumentRequest,
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

# Spec tuple: (text, bold, vert_align) where vert_align can be None, 'subscript', 'superscript'
RunSpec = Union[Tuple[str, bool], Tuple[str, bool, Optional[str]]]


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

    parts = text.split("\t")
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
    """Replace text runs in paragraph `p` while preserving `<w:pPr>` (and `<w:drawing>` if requested)."""
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
    """Set runs on the first paragraph of a table cell `<w:tc>`."""
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
    """Update 3-column signature table (used in MCCB, ĐTNĐ, MBA 1P)."""
    rows = tbl.findall("w:tr", NS)
    r0_cells = rows[0].findall("w:tc", NS)
    r1_cells = rows[1].findall("w:tc", NS)

    # Cell (0,0) has p[0] = 'Người thử' and p[1] = signature drawing
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
    """Update tab-aligned signature paragraphs (used in LA, FCO)."""
    set_p_runs(
        p_titles,
        [("\tNgười thử\tKiểm tra\tP. Giám đốc", True)],
        sz=24,
        keep_drawings=req.signatory.include_signature,
    )
    # Ensure first tab stop on p_names matches p_titles (1276) so all 3 names center cleanly
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
) -> None:
    """Clone the template data row for each item in `row_values`."""
    left_align_cols = left_align_cols or set()
    all_rows = tbl.findall("w:tr", NS)
    template_row = copy.deepcopy(all_rows[-1])
    for r in all_rows[header_row_count:]:
        tbl.remove(r)

    if not row_values:
        row_values = [["" for _ in template_row.findall("w:tc", NS)]]

    for vals in row_values:
        new_tr = copy.deepcopy(template_row)
        cells = new_tr.findall("w:tc", NS)
        for ci, tc in enumerate(cells):
            val = vals[ci] if ci < len(vals) else ""
            align = "left" if ci in left_align_cols else "center"
            set_tc_runs(tc, [(str(val), False)], sz=sz, align=align)
        tbl.append(new_tr)


def _decode_custom_signature(data_url: Optional[str]) -> Optional[bytes]:
    if not data_url:
        return None
    if "," in data_url:
        _, b64 = data_url.split(",", 1)
    else:
        b64 = data_url
    try:
        return base64.b64decode(b64)
    except Exception:
        return None


def _repack_docx(
    template_path: str,
    doc_xml_root: etree._Element,
    custom_sig_bytes: Optional[bytes] = None,
    extra_xml_overrides: Optional[Dict[str, bytes]] = None,
) -> bytes:
    extra_xml_overrides = extra_xml_overrides or {}
    out_buf = io.BytesIO()
    doc_bytes = etree.tostring(doc_xml_root, xml_declaration=True, encoding="UTF-8", standalone="yes")
    with zipfile.ZipFile(template_path, "r") as zin, zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
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


# =========================================================================
# 1. MCCB Generator
# =========================================================================
def _generate_mccb(req: ReportDocumentRequest) -> bytes:
    tpl = os.path.join(TEMPLATES_DIR, "mccb.docx")
    d = MccbData(**req.data)
    c = req.common

    with zipfile.ZipFile(tpl, "r") as z:
        root = etree.fromstring(z.read("word/document.xml"))
    body = root.find("w:body", NS)

    update_header_table(body[0], req, "BIÊN BẢN KIỂM ĐỊNH")
    set_p_runs(body[1], [("MÁY CẮT HẠ THẾ (MCCB)", True)], sz=40)
    set_p_runs(body[2], [("THÔNG TIN CÔNG TRÌNH", True)], sz=24)
    set_p_runs(body[3], [(f"Tên công trình: {c.ten_cong_trinh}", False)], sz=24)
    set_p_runs(body[4], [(f"Địa chỉ: {c.dia_chi}", False)], sz=24)
    set_p_runs(body[5], [(f"Chỉ danh: {c.chi_danh or 'MCCB 250A'}", False)], sz=24)
    set_p_runs(body[6], [(f"Đơn vị yêu cầu: {c.don_vi_yeu_cau}", False)], sz=24)
    set_p_runs(body[7], [(f"Lý do kiểm định: {c.ly_do}", False)], sz=24)
    set_p_runs(body[8], [(f"Nơi kiểm định: {c.noi_kiem_dinh}", False)], sz=24)
    set_p_runs(body[9], [(f"Ngày kiểm định: {c.ngay_kiem_dinh}", False)], sz=24)

    set_p_runs(body[10], [("THÔNG SỐ THIẾT BỊ", True)], sz=24)
    set_p_runs(body[11], [(f"Hiệu: {d.hieu}\t- Số cực: {d.so_cuc}", False)], sz=24)
    set_p_runs(body[12], [(f"Loại: {d.loai}\t- Kiểu: {d.kieu}", False)], sz=24)
    set_p_runs(body[13], [(f"Điện áp định mức: {d.dien_ap_dinh_muc}\t- Dòng điện định mức: {d.dong_dien_dinh_muc}", False)], sz=24)
    set_p_runs(body[14], [(f"Dòng điện ngắn mạch tối đa: {d.dong_ngan_mach}\t- Tần số: {d.tan_so}", False)], sz=24)
    set_p_runs(body[15], [(f"Điện áp cách điện định mức: {d.dien_ap_cach_dien}\t- Điện áp chịu xung định mức: {d.dien_ap_xung}", False)], sz=24)

    set_p_runs(body[16], [("KẾT QUẢ KIỂM ĐỊNH", True)], sz=24)
    set_p_runs(body[17], [(f"Kiểm tra bên ngoài: {d.kiem_tra_ben_ngoai}\t- Số lượng: {d.so_luong}", False)], sz=24)
    set_p_runs(body[18], [("Kết quả thử nghiệm:", False)], sz=24)

    row_vals = [
        [r.stt, r.rcd_close, r.rcd_open, r.rtx_a, r.rtx_b, r.rtx_c, r.utest, r.dong_cat, r.ket_qua, r.so_tem]
        for r in d.rows
    ]
    populate_dynamic_rows(body[19], header_row_count=2, row_values=row_vals, sz=24)

    set_p_runs(body[21], [("THIẾT BỊ KIỂM ĐỊNH: ", True), (d.thiet_bi_kiem_dinh, False)], sz=24)
    set_p_runs(body[22], [("TIÊU CHUẨN KIỂM ĐỊNH:", True)], sz=24)
    set_p_runs(body[23], [(" " + d.tieu_chuan_kiem_dinh, False)], sz=24)
    set_p_runs(body[24], [(f"KẾT LUẬN: {d.ket_luan}", True)], sz=24)

    update_table_signature(body[25], req)
    return _repack_docx(tpl, root, _decode_custom_signature(req.signatory.custom_signature_data_url))


# =========================================================================
# 2. LA Generator
# =========================================================================
def _generate_la(req: ReportDocumentRequest) -> bytes:
    tpl = os.path.join(TEMPLATES_DIR, "la.docx")
    d = LaData(**req.data)
    c = req.common

    with zipfile.ZipFile(tpl, "r") as z:
        root = etree.fromstring(z.read("word/document.xml"))
    body = root.find("w:body", NS)

    update_header_table(body[0], req, "BIÊN BẢN KIỂM ĐỊNH")
    set_p_runs(body[1], [("CHỐNG SÉT VAN (LA)", True)], sz=36)
    set_p_runs(body[2], [("THÔNG TIN CÔNG TRÌNH", True)], sz=24)
    set_p_runs(body[3], [(f"Tên công trình: {c.ten_cong_trinh}", False)], sz=24)
    set_p_runs(body[4], [(f"Địa chỉ: {c.dia_chi}", False)], sz=24)
    set_p_runs(body[5], [(f"Chỉ danh: {c.chi_danh or 'LA 18kV-10kA'}", False)], sz=24)
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
# 3. FCO Generator
# =========================================================================
def _generate_fco(req: ReportDocumentRequest) -> bytes:
    tpl = os.path.join(TEMPLATES_DIR, "fco.docx")
    d = FcoData(**req.data)
    c = req.common

    with zipfile.ZipFile(tpl, "r") as z:
        root = etree.fromstring(z.read("word/document.xml"))
    body = root.find("w:body", NS)

    update_header_table(body[0], req, "BIÊN BẢN KIỂM ĐỊNH")
    set_p_runs(body[1], [("CẦU CHÌ TỰ RƠI (FCO)", True)], sz=36)
    set_p_runs(body[2], [("THÔNG TIN CÔNG TRÌNH", True)], sz=24)
    set_p_runs(body[3], [(f"Tên công trình: {c.ten_cong_trinh}", False)], sz=24)
    set_p_runs(body[4], [(f"Địa chỉ: {c.dia_chi}", False)], sz=24)
    set_p_runs(body[5], [(f"Chỉ danh: {c.chi_danh or 'FCO – 100A'}", False)], sz=24)
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
# 4. Điện trở nối đất (ĐTNĐ) Generator
# =========================================================================
def _generate_dtnd(req: ReportDocumentRequest) -> bytes:
    tpl = os.path.join(TEMPLATES_DIR, "dtnd.docx")
    d = DtndData(**req.data)
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
    set_p_runs(body[6], [(f"Chỉ danh: {c.chi_danh or 'Điện trở nối đất'}", False)], sz=24)
    set_p_runs(body[7], [(f"Đơn vị yêu cầu: {c.don_vi_yeu_cau}", False)], sz=24)
    set_p_runs(body[8], [(f"Lý do thử nghiệm: {c.ly_do}", False)], sz=24)
    noi_tn = "Hiện trường" if c.noi_kiem_dinh in ("Tại hiện trường", "Hiện trường") else c.noi_kiem_dinh
    set_p_runs(body[9], [(f"Nơi thử nghiệm: {noi_tn}", False)], sz=24)
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
# 5. Máy biến áp 1 pha (MBA 1P) Generator (2-page standard .docx)
# =========================================================================
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
) -> etree._Element:
    """
    Create a clean centered bordered Word table.
    Each cell spec in `rows_spec` is `(runs, grid_span, v_merge)`
    where `v_merge` is None | 'restart' | 'continue'.
    """
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
            pjc.set(_w("val"), "center")
            if vmerge != "continue":
                set_p_runs(p, runs, sz=sz)
    return tbl


def _build_mba_footer_with_page_num(footer_bytes: bytes) -> bytes:
    """Append centered 'Trang X/Y' line to footer1.xml just like `44 BB MBA 1P 50KVA.doc`."""
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


def _generate_mba_1p(req: ReportDocumentRequest) -> bytes:
    tpl = os.path.join(TEMPLATES_DIR, "mba_1p_shell.docx")
    d = Mba1PData(**req.data)
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

    # I. LÝ LỊCH THIẾT BỊ
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
    body.append(
        _make_p(
            [(f"Nước sản xuất: {d.nuoc_san_xuat}\t- Năm sản xuất: {d.nam_san_xuat}", False)],
            sz=23,
            num_id=3,
            tab_stops=[6379],
        )
    )
    body.append(_make_p([(f"Tên công trình: {c.ten_cong_trinh}", False)], sz=23, num_id=3))
    body.append(_make_p([(f"Địa chỉ: {c.dia_chi}", False)], sz=23, num_id=3))
    body.append(_make_p([(f"Đơn vị yêu cầu: {c.don_vi_yeu_cau}", False)], sz=23, num_id=3))
    body.append(_make_p([(f"Lý do kiểm định: {c.ly_do}", False)], sz=23, num_id=3))
    body.append(_make_p([(f"Nơi kiểm định: {c.noi_kiem_dinh}", False)], sz=23, num_id=3))
    body.append(_make_p([(f"Ngày kiểm định: {c.ngay_kiem_dinh}", False)], sz=23, num_id=3))

    # II. QUY CÁCH KỸ THUẬT
    body.append(_make_p([("QUY CÁCH KỸ THUẬT", True)], sz=23, num_id=2, space_before=40, space_after=30))
    body.append(
        _make_p(
            [(f"Công suất định mức: {d.cong_suat_dinh_muc}\t- Số pha: {d.so_pha}\t- Tần số: {d.tan_so}", False)],
            sz=23,
            num_id=3,
            tab_stops=[4800, 7600],
        )
    )
    body.append(
        _make_p(
            [(f"Điện áp định mức: {d.dien_ap_dinh_muc}\t- Tổ đấu dây: {d.to_dau_day}", False)],
            sz=23,
            num_id=3,
            tab_stops=[4800],
        )
    )

    # III. KẾT QUẢ KIỂM ĐỊNH
    body.append(_make_p([("KẾT QUẢ KIỂM ĐỊNH", True)], sz=23, num_id=2, space_before=40, space_after=30))
    body.append(_make_p([(f"Kiểm tra bên ngoài: {d.kiem_tra_ben_ngoai}", False)], sz=23, num_id=4))
    body.append(_make_p([("Điện trở cách điện: (MΩ)", False)], sz=23, num_id=4))

    # Table 2: Điện trở cách điện
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
            [
                ([(r.doi_tuong_do, False)], 1, None),
                ([(r.r60, False)], 1, None),
                ([(r.r15, False)], 1, None),
                ([(r.kht, False)], 1, None),
            ]
        )
    body.append(_make_bordered_table([2600, 2200, 2200, 2000], ins_rows, sz=22))

    # Item 3: Điện trở một chiều cuộn dây
    body.append(_make_p([("Điện trở một chiều cuộn dây:", False)], sz=23, num_id=4, space_before=50, space_after=30))
    n_taps = max(len(d.dien_tro_cao_ap), 1)
    tap_w = 5400 // n_taps
    dc_widths = [1600] + [tap_w] * n_taps + [1200, 1200]
    dc_rows = [
        [
            ([("", True)], 1, None),
            ([("Cuộn dây cao áp (Ω)", True)], n_taps, None),
            ([("Cuộn dây hạ áp (mΩ)", True)], 2, None),
        ],
        [([("Nấc", False)], 1, None)]
        + [([(str(i + 1), False)], 1, None) for i in range(n_taps)]
        + [([("HA 1", False)], 1, None), ([("HA 2", False)], 1, None)],
        [([("Kết quả đo", False)], 1, None)]
        + [([(d.dien_tro_cao_ap[i], False)], 1, None) for i in range(n_taps)]
        + [([(d.dien_tro_ha_1, False)], 1, None), ([(d.dien_tro_ha_2, False)], 1, None)],
    ]
    body.append(_make_bordered_table(dc_widths, dc_rows, sz=22))

    # Item 4: Tỉ số biến áp
    body.append(_make_p([("Tỉ số biến áp:", False)], sz=23, num_id=4, space_before=50, space_after=30))
    n_h1 = max(len(d.ti_so_ha_1), 1)
    n_h2 = max(len(d.ti_so_ha_2), 1)
    ratio_cell_w = 8400 // (n_h1 + n_h2)
    ratio_widths = [1400] + [ratio_cell_w] * (n_h1 + n_h2)
    ratio_rows = [
        [
            ([("Cao", True)], 1, None),
            ([("Hạ 1", True)], n_h1, None),
            ([("Hạ 2", True)], n_h2, None),
        ],
        [([("Nấc", False)], 1, None)]
        + [([(str(i + 1), False)], 1, None) for i in range(n_h1)]
        + [([(str(i + 1), False)], 1, None) for i in range(n_h2)],
        [([("Kết quả đo", False)], 1, None)]
        + [([(d.ti_so_ha_1[i], False)], 1, None) for i in range(n_h1)]
        + [([(d.ti_so_ha_2[i], False)], 1, None) for i in range(n_h2)],
    ]
    body.append(_make_bordered_table(ratio_widths, ratio_rows, sz=21))

    # Item 5: Thí nghiệm không tải
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

    # --- PAGE 2 ---
    # Item 6: Thí nghiệm ngắn mạch
    body.append(
        _make_p(
            [("Thí nghiệm ngắn mạch:", False)],
            sz=23,
            num_id=4,
            space_before=80,
            space_after=40,
            page_break_before=True,
        )
    )
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

    # Item 7: Thử điện áp tăng cao
    body.append(_make_p([("Thử điện áp tăng cao:", False)], sz=23, num_id=4, space_before=60, space_after=40))
    ac_rows = [
        [
            ([("Đối tượng thử", True)], 1, None),
            ([("U", True), ("thử", True, "subscript"), (" (kV)", True)], 1, None),
            ([("Thời gian thử", True)], 1, None),
        ]
    ]
    for r in d.dien_ap_tang_cao_rows:
        ac_rows.append(
            [
                ([(r.doi_tuong_thu, False)], 1, None),
                ([(r.u_thu, False)], 1, None),
                ([(r.thoi_gian, False)], 1, None),
            ]
        )
    body.append(_make_bordered_table([2800, 1800, 2200], ac_rows, sz=22))

    # IV. THIẾT BỊ KIỂM ĐỊNH & V. KẾT LUẬN
    body.append(
        _make_p(
            [("THIẾT BỊ KIỂM ĐỊNH: ", True), (d.thiet_bi_kiem_dinh, False)],
            sz=24,
            num_id=2,
            space_before=100,
            space_after=60,
        )
    )
    body.append(_make_p([(f"KẾT LUẬN: {d.ket_luan}", True)], sz=24, num_id=2, space_before=60, space_after=120))

    body.append(sig_tbl)
    body.append(sectPr)

    new_footer = _build_mba_footer_with_page_num(footer1_bytes)
    return _repack_docx(
        tpl,
        root,
        _decode_custom_signature(req.signatory.custom_signature_data_url),
        extra_xml_overrides={"word/footer1.xml": new_footer},
    )


def generate_report_docx(req: ReportDocumentRequest) -> bytes:
    generators = {
        "mba_1p": _generate_mba_1p,
        "mccb": _generate_mccb,
        "la": _generate_la,
        "fco": _generate_fco,
        "dtnd": _generate_dtnd,
    }
    if req.report_type not in generators:
        raise ValueError(f"Unsupported report_type: {req.report_type}")
    return generators[req.report_type](req)
