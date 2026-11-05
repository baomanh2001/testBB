"""Dựng mẫu 93 (MÁY CẮT HẠ THẾ – ACB) từ khung của mẫu 45.

Nguồn nội dung: ``093 BB ACB 2500A 016138.doc`` (số 50931026/BB-TC). Chép
nguyên văn thứ tự mục, nhãn và đơn vị của bản .doc.

Khác mẫu 45 (MCCB) ở chỗ ACB có thêm 2 dòng thông số cách điện và dùng đúng
tên loại "ACB" trong chỉ danh/kết luận — nếu dùng lẫn mẫu 45 thì bản in sai
tên thiết bị.

Chạy::

    python tools/build_template_93.py
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
OUT = ROOT / "templates" / "93 BB ACB.docx"

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def build(out: Path = OUT) -> Path:
    doc = docx.Document(str(SRC))
    header_tbl = copy.deepcopy(doc.element.body.find(W + "tbl"))
    body = doc.element.body
    for child in list(body):
        if child.tag != W + "sectPr":
            body.remove(child)
    body.insert(0, header_tbl)

    _para(doc, "MÁY CẮT HẠ THẾ (ACB)", bold=True, size=40, align="center",
          space_before=200, space_after=120)

    _para(doc, "THÔNG TIN CÔNG TRÌNH", style_num=2, bold=True,
          space_before=60, space_after=60)
    for line in [
        "Tên công trình:",
        "Địa chỉ:",
        "Chỉ danh:",
        "Đơn vị yêu cầu:",
        "Lý do thử nghiệm:",
        "Nơi thử nghiệm:",
        "Ngày thử nghiệm:",
    ]:
        _para(doc, line, size=24)

    _para(doc, "THÔNG SỐ THIẾT BỊ", style_num=2, bold=True,
          space_before=120, space_after=60)
    for left, right in [
        ("Hiệu:", "- Số cực:"),
        ("Loại: ACB", "- Kiểu:"),
        ("Điện áp định mức:", "- Dòng điện định mức:"),
        ("Dòng điện ngắn mạch tối đa:", "- Tần số:"),
        ("Điện áp cách điện định mức:", "- Điện áp chịu xung định mức:"),
    ]:
        _para(doc, f"{left}\t{right}", size=24)

    _para(doc, "KẾT QUẢ THỬ NGHIỆM", style_num=2, bold=True,
          space_before=120, space_after=60)
    _para(doc, "Kiểm tra bên ngoài:\t- Số lượng:", size=24)
    _para(doc, "Kết quả thí nghiệm:", size=24, space_before=60, space_after=60)

    _table(
        doc,
        [
            ["STT", "R cách điện (MΩ)", "", "R tiếp xúc (µΩ)", "", "",
             "Utest (kV/1’)", "Đóng\nCắt", "Kết quả", "Số tem"],
            ["", "Close", "Open", "Pha A", "Pha B", "Pha C", "", "", "", ""],
            ["1", "", "", "", "", "", "", "", "", ""],
            ["2", "", "", "", "", "", "", "", "", ""],
            ["3", "", "", "", "", "", "", "", "", ""],
        ],
        widths=[700, 1300, 1300, 1100, 1100, 1100, 1200, 1100, 1200, 1300],
        merges=[(0, 0, 1, 0), (0, 1, 0, 2), (0, 3, 0, 5), (0, 6, 1, 6),
                (0, 7, 1, 7), (0, 8, 1, 8), (0, 9, 1, 9)],
        header_rows=2,
    )

    _para(doc, "THIẾT BỊ KIỂM ĐỊNH:", size=24, space_before=120)
    _para(doc, "TIÊU CHUẨN KIỂM ĐỊNH: QCVN QTĐ-5: 2009/BCT; QT/TNMCĐ", size=24)
    _para(doc, "KẾT LUẬN:", size=24, space_before=60)

    _para(doc, "", size=24)
    _table(
        doc,
        [["Người thử", "Kiểm tra", "P. Giám đốc"], ["", "", ""]],
        widths=[3000, 3000, 3000],
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return out


if __name__ == "__main__":
    p = build()
    d = docx.Document(str(p))
    print(f"đã tạo {p.name}  ({p.stat().st_size} B, {len(d.tables)} bảng)")
