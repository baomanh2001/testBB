"""Dựng lại mẫu 44 (MBA 1 pha) thành file .docx chuẩn layout công ty.

Bối cảnh: ``44 BB MBA 1P 50KVA.doc`` là định dạng Word 97 (OLE2) cũ. Word vẫn
mở được, nhưng để bộ điền form chạy đồng nhất và **giữ nguyên logo/header/
footer/kẻ bảng** như 4 mẫu còn lại, ta dựng mẫu 44 thành ``.docx`` bằng cách
nhân bản toàn bộ "khung" của ``45 MCCB 250A.docx`` (cùng bộ style, header 3
loại, footer, khổ giấy, lề) rồi thay phần thân bằng nội dung của bản .doc gốc.

Nội dung chép nguyên văn từ bản .doc: đúng thứ tự mục I → V, đúng nhãn, đúng
đơn vị. Bản .doc gốc vẫn được giữ trong ``legacy/`` để đối chiếu.

Chạy::

    python tools/build_template_44.py
"""

from __future__ import annotations

import copy
import shutil
import sys
from pathlib import Path

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "45 MCCB 250A.docx"          # nguồn khung (style, header, footer)
OUT = ROOT / "templates" / "44 BB MBA 1P.docx"
LEGACY = ROOT / "legacy" / "44 BB MBA 1P 50KVA.doc"

W_P = qn("w:p")


# --------------------------------------------------------------------------- #
# Tiện ích XML
# --------------------------------------------------------------------------- #
def _clear_body(doc):
    body = doc.element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)


def _para(doc, text="", *, style_num=None, bold=False, size=None, align=None,
          indent=None, tabs=None, space_before=None, space_after=None):
    p = OxmlElement("w:p")
    ppr = OxmlElement("w:pPr")
    if style_num is not None:
        numpr = OxmlElement("w:numPr")
        ilvl = OxmlElement("w:ilvl")
        ilvl.set(qn("w:val"), "0")
        numid = OxmlElement("w:numId")
        numid.set(qn("w:val"), str(style_num))
        numpr.append(ilvl)
        numpr.append(numid)
        ppr.append(numpr)
    if tabs:
        tabs_el = OxmlElement("w:tabs")
        for pos in tabs:
            tab = OxmlElement("w:tab")
            tab.set(qn("w:val"), "left")
            tab.set(qn("w:pos"), str(pos))
            tabs_el.append(tab)
        ppr.append(tabs_el)
    spacing = OxmlElement("w:spacing")
    if space_before is not None:
        spacing.set(qn("w:before"), str(space_before))
    if space_after is not None:
        spacing.set(qn("w:after"), str(space_after))
    if space_before is not None or space_after is not None:
        ppr.append(spacing)
    if indent is not None:
        ind = OxmlElement("w:ind")
        for k, v in indent.items():
            ind.set(qn(f"w:{k}"), str(v))
        ppr.append(ind)
    if align is not None:
        jc = OxmlElement("w:jc")
        jc.set(qn("w:val"), align)
        ppr.append(jc)
    rpr = OxmlElement("w:rPr")
    if bold:
        rpr.append(OxmlElement("w:b"))
        rpr.append(OxmlElement("w:bCs"))
    sz = size or 24
    for tag in ("w:sz", "w:szCs"):
        el = OxmlElement(tag)
        el.set(qn("w:val"), str(sz))
        rpr.append(el)
    ppr.append(rpr)
    p.append(ppr)

    if text:
        for chunk in text.split("\t"):
            if chunk != text.split("\t")[0] or text.startswith("\t"):
                pass
        parts = text.split("\t")
        for i, part in enumerate(parts):
            if i:
                r = OxmlElement("w:r")
                r.append(_run_rpr(bold, sz))
                r.append(OxmlElement("w:tab"))
                p.append(r)
            if part:
                r = OxmlElement("w:r")
                r.append(_run_rpr(bold, sz))
                t = OxmlElement("w:t")
                t.set(qn("xml:space"), "preserve")
                t.text = part
                r.append(t)
                p.append(r)
    doc.element.body.insert(len(doc.element.body) - 1, p)
    return p


def _run_rpr(bold: bool, sz: int):
    rpr = OxmlElement("w:rPr")
    if bold:
        rpr.append(OxmlElement("w:b"))
        rpr.append(OxmlElement("w:bCs"))
    for tag in ("w:sz", "w:szCs"):
        el = OxmlElement(tag)
        el.set(qn("w:val"), str(sz))
        rpr.append(el)
    return rpr


def _append_to_body(doc, el):
    body = doc.element.body
    body.insert(len(body) - 1, el)


# --------------------------------------------------------------------------- #
# Bảng
# --------------------------------------------------------------------------- #
def _table(doc, rows: list[list[str]], widths: list[int], *, header_rows=1,
           merges: list[tuple] | None = None):
    """Tạo bảng có viền kẻ giống bảng của mẫu 45 (viền đơn, canh giữa)."""
    n_rows, n_cols = len(rows), len(rows[0])
    t = doc.add_table(rows=n_rows, cols=n_cols)
    # chuyển bảng vào cuối body nhưng trước sectPr
    _append_to_body(doc, t._tbl)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = "Table Grid"
    for (r0, c0, r1, c1) in merges or []:
        a = t.cell(r0, c0)
        b = t.cell(r1, c1)
        a.merge(b)
    for j, w in enumerate(widths):
        if j >= n_cols:
            break
        for r in t.rows:
            r.cells[j].width = Pt(w / 20)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = t.cell(i, j)
            cell.width = Pt(widths[j] / 20)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(val)
            run.font.size = Pt(11 if i < header_rows else 12)
            run.bold = i < header_rows
            if i >= header_rows and j == 0:
                run.bold = False
    return t


def build(out: Path = OUT) -> Path:
    doc = docx.Document(str(SRC))
    # giữ lại bảng tiêu đề (logo + SỐ + NGÀY) của mẫu 45 rồi mới xoá thân bài
    header_tbl = copy.deepcopy(doc.element.body.find(qn("w:tbl")))
    _clear_body(doc)
    doc.element.body.insert(0, header_tbl)

    # ---------------- Tiêu đề ----------------
    _para(doc, "MÁY BIẾN ÁP 1 PHA", bold=True, size=40, align="center",
          space_before=200, space_after=120)

    # ---------------- I. LÝ LỊCH THIẾT BỊ ----------------
    _para(doc, "LÝ LỊCH THIẾT BỊ", style_num=2, bold=True, space_before=60, space_after=60)
    _para(doc, "Hiệu máy: EMC\t- Số tem: 017246", style_num=3, tabs=[284, 6379],
          space_before=60, space_after=60)
    _para(doc, "Số máy: 04080968\t- Năm sản xuất: 2004", style_num=3, tabs=[284, 6379],
          space_before=60, space_after=60)
    _para(doc, "Nước sản xuất: Việt Nam\t- Tần số: 50Hz", style_num=3, tabs=[284, 6379],
          space_before=60, space_after=60)
    _para(doc, "Tên công trình: Trạm biến áp 50kVA - DOANH NGHIỆP TƯ NHÂN E-GREEN",
          style_num=3, space_before=60, space_after=60)
    _para(doc, "Địa chỉ: Khu phố Gia Huỳnh, Phường Trảng Bàng, Tỉnh Tây Ninh, Việt Nam",
          style_num=3, space_before=60, space_after=60)
    _para(doc, "Đơn vị yêu cầu: DOANH NGHIỆP TƯ NHÂN E-GREEN", style_num=3,
          space_before=60, space_after=60)
    _para(doc, "Lý do kiểm định: Sau sự cố", style_num=3, space_before=60, space_after=60)
    _para(doc, "Nơi kiểm định: Tại hiện trường", style_num=3, space_before=60, space_after=60)
    _para(doc, "Ngày kiểm định: 01/11/2026", style_num=3, space_before=60, space_after=60)

    # ---------------- II. QUY CÁCH KỸ THUẬT ----------------
    _para(doc, "QUY CÁCH KỸ THUẬT", style_num=2, bold=True, space_before=120, space_after=60)
    _para(doc, "Công suất định mức: 50kVA\t- Số pha: 01\t- Tần số: 50Hz",
          style_num=3, tabs=[284, 3400, 6379], space_before=60, space_after=60)
    _para(doc, "Điện áp định mức: 12,7/0,23kV\t- Tổ đấu dây: I/I0",
          style_num=3, tabs=[284, 5000], space_before=60, space_after=60)

    # ---------------- III. KẾT QUẢ KIỂM ĐỊNH ----------------
    _para(doc, "KẾT QUẢ KIỂM ĐỊNH", style_num=2, bold=True, space_before=200,
          space_after=120)
    # số thứ tự 1., 2., 3. … do Word sinh ra (numId 4), không gõ tay
    _para(doc, "Kiểm tra bên ngoài: Bình thường", style_num=4, space_before=60, space_after=60)

    _para(doc, "Điện trở cách điện: (MΩ)", style_num=4, bold=True, space_before=60, space_after=60)
    _table(
        doc,
        [
            ["Đối tượng đo", "R60'' (MΩ)", "R15'' (MΩ)", "Kht"],
            ["(Cao+Vỏ) - Hạ 1", "2760", "2106", "1,31"],
            ["(Cao+Vỏ) - Hạ 2", "2550", "1902", "1,34"],
            ["Hạ 1 - Hạ 2", "1790", "1376", "1,30"],
        ],
        widths=[4200, 2400, 2400, 1800],
        merges=[(0, 1, 0, 3)],
    )
    _para(doc, "", size=12)

    _para(doc, "Điện trở một chiều cuộn dây:", style_num=4, bold=True, space_before=120, space_after=60)
    _table(
        doc,
        [
            ["", "Cuộn dây cao áp (Ω)", "", "", "", "", "Cuộn dây hạ áp (mΩ)", ""],
            ["Nấc", "1", "2", "3", "4", "5", "HA 1", "HA 2"],
            ["Kết quả đo", "16,42", "15,98", "15,57", "15,12", "14,68", "8,832", "8,824"],
        ],
        widths=[2000, 1200, 1200, 1200, 1200, 1200, 1400, 1400],
        merges=[(0, 0, 1, 0), (0, 1, 0, 5), (0, 6, 0, 7)],
    )
    _para(doc, "", size=12)

    _para(doc, "Tỉ số biến áp:", style_num=4, bold=True, space_before=120, space_after=60)
    _table(
        doc,
        [
            ["", "Hạ 1", "", "", "", "", "Hạ 2", "", "", "", ""],
            ["Nấc", "1", "2", "3", "4", "5", "1", "2", "3", "4", "5"],
            ["Kết quả đo", "57,98", "56,59", "55,21", "53,83", "52,46",
             "57,95", "56,57", "55,25", "53,87", "52,44"],
        ],
        widths=[1500, 900, 900, 900, 900, 900, 900, 900, 900, 900, 900],
        merges=[(0, 0, 1, 0), (0, 1, 0, 5), (0, 6, 0, 10)],
    )
    _para(doc, "", size=12)

    _para(doc, "Thí nghiệm không tải:", style_num=4, bold=True, space_before=120, space_after=60)
    _table(
        doc,
        [
            ["Đối tượng đo", "U0(V)", "I0 (A)", "I0%", "P0(W)"],
            ["Kết quả đo", "230", "1,58", "0,73", "97,6"],
        ],
        widths=[3400, 1800, 1800, 1800, 1800],
    )
    _para(doc, "", size=12)

    _para(doc, "Thí nghiệm ngắn mạch:", style_num=4, bold=True, space_before=120, space_after=60)
    _table(
        doc,
        [
            ["Đối tượng đo", "UN (V)", "UN (%)", "IN", "PN75 (W)"],
            ["Kết quả đo", "304,7", "2,4", "3,94", "563,2"],
        ],
        widths=[3400, 1800, 1800, 1800, 1800],
    )
    _para(doc, "", size=12)

    _para(doc, "Thử điện áp tăng cao:", style_num=4, bold=True, space_before=120, space_after=60)
    _table(
        doc,
        [
            ["Đối tượng thử", "Uthử (kV)", "Thời gian thử"],
            ["Cuộn dây cao áp", "50", "1 phút"],
            ["Cuộn dây hạ áp", "3", "1 phút"],
        ],
        widths=[4000, 2400, 2600],
    )

    # ---------------- IV + V ----------------
    _para(doc,
          "THIẾT BỊ KIỂM ĐỊNH: Kyoritsu 3125A, C.A 6255, DTR 8510, HVTS-70/50, "
          "Multimeter, Variac.",
          style_num=2, space_before=200, space_after=100, indent={"left": 426, "hanging": 437})
    _para(doc, "KẾT LUẬN: Máy biến áp 1 pha trên đạt yêu cầu đóng điện vận hành.",
          style_num=2, bold=True, space_before=60, space_after=100,
          indent={"left": 426, "hanging": 437})

    # ---------------- Chữ ký ----------------
    sig = doc.add_table(rows=2, cols=3)
    _append_to_body(doc, sig._tbl)
    sig.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, label in enumerate(["Người thử", "Kiểm tra", "P. Giám đốc"]):
        p = sig.cell(0, j).paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(label)
        r.bold = True
        r.font.size = Pt(12)
    for j, name in enumerate(["Nguyễn Trung Nghĩa", "Nguyễn Minh Quân", "Nguyễn Nhật Tân"]):
        p = sig.cell(1, j).paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(name)
        r.bold = True
        r.font.size = Pt(12)
    for r in sig.rows:
        r.height = Pt(120)

    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))

    LEGACY.parent.mkdir(parents=True, exist_ok=True)
    if not LEGACY.exists():
        shutil.copy2(ROOT / "44 BB MBA 1P 50KVA.doc", LEGACY)
    return out


if __name__ == "__main__":
    path = build()
    print(f"Đã tạo {path.relative_to(ROOT)}")
    sys.exit(0)
