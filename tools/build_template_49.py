"""Dựng mẫu 49 (MBA 3 pha) thành .docx từ khung của mẫu 45.

Nguồn nội dung: ``092 BB MBA 1500kVA.doc`` – biên bản MBA 3 pha của công ty
(số 50921026/BB-TC). Nội dung chép **nguyên văn** từ bản .doc: đúng thứ tự mục
I → V, đúng nhãn (kể cả dấu ngoặc kép ″ trong R60″/R15″, khác mẫu 44 dùng ''),
đúng đơn vị và đúng bố cục 4 bảng đặc thù của 3 pha:

* Điện trở cách điện: ``Cao – Vỏ``, ``Cao – Hạ``, ``Hạ – Vỏ``
* Điện trở một chiều: cuộn cao áp **AB / BC / CA** × 5 nấc + 1 ô gộp hạ áp
* Tỉ số biến áp: ``K1``, ``K2``, ``K3`` × 5 nấc
* Thử điện áp tăng cao: ``Cao – (Hạ + vỏ)``, ``Hạ – (Cao + vỏ)``

Chạy::

    python tools/build_template_49.py
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_template_44 import _append_to_body, _para, _table  # noqa: E402

SRC = ROOT / "45 MCCB 250A.docx"          # nguồn khung (style, header, footer, logo)
OUT = ROOT / "templates" / "49 BB MBA 3P.docx"
LEGACY = ROOT / "092 BB MBA 1500kVA.doc"  # bản .doc gốc để đối chiếu

W_TBL = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tbl"


def build(out: Path = OUT) -> Path:
    doc = docx.Document(str(SRC))
    # giữ bảng tiêu đề (logo + SỐ + NGÀY) rồi xoá thân bài
    header_tbl = copy.deepcopy(doc.element.body.find(W_TBL))
    body = doc.element.body
    for child in list(body):
        if child.tag != "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sectPr":
            body.remove(child)
    body.insert(0, header_tbl)

    # ---------------- Tiêu đề ----------------
    _para(doc, "MÁY BIẾN ÁP 3 PHA", bold=True, size=40, align="center",
          space_before=200, space_after=120)

    # ---------------- I. LÝ LỊCH THIẾT BỊ ----------------
    _para(doc, "LÝ LỊCH THIẾT BỊ", style_num=2, bold=True, space_before=60, space_after=60)
    for left, right in [
        ("Hiệu máy: THIBIDI", "- Số tem: 016140"),
        ("Số máy: 103150017", "- Năm sản xuất: 2010"),
    ]:
        _para(doc, f"{left}\t{right}", style_num=3, tabs=[284, 6379],
              space_before=60, space_after=60)
    _para(doc, "Nước sản xuất: Việt Nam", style_num=3, space_before=60, space_after=60)
    _para(doc, "Tên công trình: Trạm biến áp 1500kVA – CÔNG TY TNHH MỘT THÀNH VIÊN "
               "DREAM MEKONG", style_num=3, space_before=60, space_after=60)
    _para(doc, "Địa chỉ: Ấp An Thái, Xã Hội Cư, Tỉnh Đồng Tháp, Việt Nam", style_num=3,
          space_before=60, space_after=60)
    _para(doc, "Đơn vị yêu cầu: CÔNG TY TNHH MỘT THÀNH VIÊN DREAM MEKONG", style_num=3,
          space_before=60, space_after=60)
    _para(doc, "Lý do kiểm định: Định kỳ", style_num=3, space_before=60, space_after=60)
    _para(doc, "Nơi kiểm định: Hiện trường", style_num=3, space_before=60, space_after=60)
    _para(doc, "Ngày kiểm định: 25/10/2026", style_num=3, space_before=60, space_after=60)

    # ---------------- II. QUY CÁCH KỸ THUẬT ----------------
    _para(doc, "QUY CÁCH KỸ THUẬT", style_num=2, bold=True, space_before=120, space_after=60)
    _para(doc, "Công suất định mức: 1500kVA\t- Số pha: 03\t- Tần số: 50 Hz",
          style_num=3, tabs=[284, 3400, 6379], space_before=60, space_after=60)
    _para(doc, "Điện áp định mức: 22/0.4kV\t- Tổ đấu dây: Dyn11", style_num=3,
          tabs=[284, 5000], space_before=60, space_after=60)

    # ---------------- III. KẾT QUẢ KIỂM ĐỊNH ----------------
    _para(doc, "KẾT QUẢ KIỂM ĐỊNH", style_num=2, bold=True, space_before=200,
          space_after=120)
    _para(doc, "Kiểm tra bên ngoài: Bình thường\t", style_num=4, space_before=60,
          space_after=60)

    _para(doc, "Điện trở cách điện: (MΩ)\t- Nhiệt độ: 34⁰C", style_num=4, bold=True,
          space_before=60, space_after=60)
    _table(
        doc,
        [
            ["Đối tượng đo", "R60″ (MΩ)", "R15″ (MΩ)", "Kht"],
            ["Cao – Vỏ", "15300", "11300", "1,35"],
            ["Cao – Hạ", "13700", "10200", "1,34"],
            ["Hạ – Vỏ", "8200", "6200", "1,32"],
        ],
        widths=[4200, 2400, 2400, 1800],
        merges=[(0, 1, 0, 3)],
    )
    _para(doc, "", size=12)

    _para(doc, "Điện trở một chiều cuộn dây:", style_num=4, bold=True,
          space_before=120, space_after=60)
    _table(
        doc,
        [
            ["", "Cuộn dây cao áp (Ω)", "", "", "Cuộn dây hạ áp (mΩ)"],
            ["Nấc", "AB", "BC", "CA", "an: 0,885\nbn: 0,887\ncn: 0,889"],
            ["1", "3,413", "3,418", "3,421", ""],
            ["2", "3,332", "3,336", "3,339", ""],
            ["3", "3,251", "3,255", "3,258", ""],
            ["4", "3,169", "3,174", "3,177", ""],
            ["5", "3,088", "3,092", "3,095", ""],
        ],
        widths=[1200, 1600, 1600, 1600, 2800],
        merges=[(0, 0, 1, 0), (0, 1, 0, 3), (0, 4, 1, 4), (2, 4, 6, 4)],
        header_rows=2,
    )
    _para(doc, "", size=12)

    _para(doc, "Tỉ số biến áp:", style_num=4, bold=True, space_before=120, space_after=60)
    _table(
        doc,
        [
            ["Nấc", "K1", "K2", "K3"],
            ["1", "57,759", "57,763", "57,764"],
            ["2", "56,384", "56,387", "56,388"],
            ["3", "55,019", "55,012", "55,013"],
            ["4", "53,633", "53,637", "53,638"],
            ["5", "52,258", "52,261", "52,262"],
        ],
        widths=[1600, 2400, 2400, 2400],
        header_rows=1,
    )
    _para(doc, "", size=12)

    _para(doc, "Thử nghiệm không tải: Hở mạch cuộn cao áp, đưa điện áp vào cuộn hạ áp:",
          style_num=4, bold=True, space_before=120, space_after=60)
    _table(
        doc,
        [
            ["Đối tượng đo", "U0(V)", "I0(A)", "I0%", "P0(W)"],
            ["Kết quả đo", "400", "5,19", "0,24", "1210,3"],
        ],
        widths=[3400, 1800, 1800, 1800, 1800],
    )
    _para(doc, "", size=12)

    _para(doc, "Thử nghiệm ngắn mạch: Đấu tắt cuộn dây hạ áp, đưa điện áp vào phía cuộn "
               "dây cao áp", style_num=4, bold=True, space_before=120, space_after=60)
    _table(
        doc,
        [
            ["Đối tượng đo", "UN(V)", "UN(%)", "IN(A)", "PN75(W)"],
            ["Kết quả đo", "1280,4", "5,82", "39,36", "12423,3"],
        ],
        widths=[3400, 1800, 1800, 1800, 1800],
    )
    _para(doc, "", size=12)

    _para(doc, "Thử nghiệm điện áp tăng cao:", style_num=4, bold=True,
          space_before=120, space_after=60)
    _table(
        doc,
        [
            ["Đối tượng thử", "Uthử(kV)", "Thời gian thử"],
            ["Cao – (Hạ + vỏ)", "50", "1 phút"],
            ["Hạ – (Cao + vỏ)", "3", "1 phút"],
        ],
        widths=[4000, 2400, 2600],
    )

    # ---------------- IV + V ----------------
    _para(doc, "THIẾT BỊ KIỂM ĐỊNH: Kyoritsu 3125A, C.A 6255, DTR 8510, HVTS-70/50, "
               "Multimeter, Variac.", style_num=2, space_before=200, space_after=100,
          indent={"left": 426, "hanging": 437})
    _para(doc, "KẾT LUẬN: Máy biến áp 3 pha trên đạt yêu cầu đóng điện vận hành",
          style_num=2, bold=True, space_before=60, space_after=100,
          indent={"left": 426, "hanging": 437})

    # ---------------- Chữ ký ----------------
    sig = doc.add_table(rows=2, cols=3)
    _append_to_body(doc, sig._tbl)
    sig.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, label in enumerate(["Người thử", "Kiểm tra", "P. Giám đốc"]):
        para = sig.cell(0, j).paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(label)
        run.bold = True
        run.font.size = Pt(12)
    for j, name in enumerate(["Nguyễn Trung Nghĩa", "Nguyễn Minh Quân", "Nguyễn Nhật Tân"]):
        para = sig.cell(1, j).paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(name)
        run.bold = True
        run.font.size = Pt(12)
    for row in sig.rows:
        row.height = Pt(120)

    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return out


if __name__ == "__main__":
    path = build()
    print(f"Đã tạo {path.relative_to(ROOT)}")
    sys.exit(0)
