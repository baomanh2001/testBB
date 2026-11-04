"""Bộ công cụ tự động điền biên bản kiểm định thiết bị điện lực.

Luồng sử dụng::

    Ảnh hiện trường  ->  LLM trích xuất  ->  JSON chuẩn  ->  bienban  ->  44..48.docx

``bienban`` chỉ nhận **JSON** (hợp đồng dữ liệu với bước trích xuất ảnh) rồi
điền vào đúng file mẫu Word của Công ty CP Thí nghiệm Điện Toàn Cầu, giữ
nguyên logo, header/footer, cách đánh số La Mã, kẻ bảng và chữ ký số có sẵn
trong mẫu.
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__ = ["__version__"]
