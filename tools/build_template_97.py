"""Dựng mẫu 97 (THÔNG TUYẾN CÁP NGẦM TRUNG THẾ) từ khung mẫu 45.

Nguồn: ``097 BB Thông tuyến cáp ngầm TT.doc`` (số 50971026/BB-TC).

Mẫu này khác hẳn các mẫu khác: đo **theo pha** (Pha 1/2/3 so với 2 pha còn
lại + vỏ) ở hai bảng — điện trở cách điện và điện áp một chiều tăng cao.

Chạy::

    python tools/build_template_97.py
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import docx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_template_44 import _para, _table  # noqa: E402

SRC = ROOT / "45 MCCB 250A.docx"
OUT = ROOT / "templates" / "97 BB cáp ngầm.docx"

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def build(out: Path = OUT) -> Path:
    doc = docx.Document(str(SRC))
    header_tbl = copy.deepcopy(doc.element.body.find(W + "tbl"))
    body = doc.element.body
    for child in list(body):
        if child.tag != W + "sectPr":
            body.remove(child)
    body.insert(0, header_tbl)

    _para(doc, "THÔNG TUYẾN CÁP NGẦM TRUNG THẾ", bold=True, size=40,
          align="center", space_before=200, space_after=120)

    _para(doc, "THÔNG TIN CÔNG TRÌNH", style_num=2, bold=True,
          space_before=60, space_after=60)
    for line in ["Tên công trình:", "Địa chỉ:", "Chỉ danh:", "Đơn vị yêu cầu:",
                 "Lý do kiểm định:", "Nơi kiểm định:", "Ngày kiểm định:"]:
        _para(doc, line, size=24)

    _para(doc, "THÔNG SỐ THIẾT BỊ", style_num=2, bold=True,
          space_before=120, space_after=60)
    _para(doc, "- Số tem:", size=24)
    for left, right in [
        ("Đoạn cáp đi từ:", "- Đến:"),
        ("Loại cáp:", "- Tiết diện:"),
        ("Điện áp định mức:", "- Tần số:"),
    ]:
        _para(doc, f"{left}\t{right}", size=24)

    _para(doc, "KẾT QUẢ KIỂM ĐỊNH", style_num=2, bold=True,
          space_before=120, space_after=60)
    _para(doc, "Kiểm tra bên ngoài:", size=24)

    _para(doc, "Điện trở cách điện:\t- Nhiệt độ:", size=24,
          space_before=60, space_after=60)
    _table(
        doc,
        [
            ["Đối tượng đo", "Tiêu chuẩn (MΩ)", "Số liệu đo (MΩ)"],
            ["Pha 1 – (2+3+vỏ)", "", ""],
            ["Pha 2 – (1+3+vỏ)", "", ""],
            ["Pha 3 – (1+2+vỏ)", "", ""],
        ],
        widths=[3600, 2800, 2800],
        header_rows=1,
    )

    _para(doc, "Điện áp một chiều tăng cao:", size=24,
          space_before=120, space_after=60)
    _table(
        doc,
        [
            ["Đối tượng đo", "Thời gian (phút)", "Điện áp thử nghiệm (kV)",
             "Dòng rò (µA)"],
            ["Pha 1 – (2+3+vỏ)", "", "", ""],
            ["Pha 2 – (1+3+vỏ)", "", "", ""],
            ["Pha 3 – (1+2+vỏ)", "", "", ""],
        ],
        widths=[2900, 1900, 2500, 1900],
        header_rows=1,
    )

    _para(doc, "THIẾT BỊ KIỂM ĐỊNH:", size=24, space_before=120)
    _para(doc, "TIÊU CHUẨN KIỂM ĐỊNH: QCVN QTĐ-5,6,7: 2009/BCT", size=24)
    _para(doc, "KẾT LUẬN:", size=24, space_before=60)

    _para(doc, "", size=24)
    _table(doc, [["Người thử", "Kiểm tra", "P. Giám đốc"], ["", "", ""]],
           widths=[3000, 3000, 3000])

    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return out


if __name__ == "__main__":
    p = build()
    d = docx.Document(str(p))
    print(f"đã tạo {p.name}  ({p.stat().st_size} B, {len(d.tables)} bảng)")
