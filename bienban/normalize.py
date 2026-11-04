"""Chuẩn hoá dữ liệu theo quy tắc của công ty.

Mọi giá trị trước khi ghi vào Word đều đi qua module này:

* ngày tháng  -> ``dd/mm/yyyy`` (2 chữ số)
* số máy / số tem / số công tơ -> bỏ mọi ký tự không phải chữ số
  (tránh lỗi OCR đọc ``O`` thành ``0``, ``l`` thành ``1``...)
* số đo -> luôn dùng **dấu phẩy thập phân** kiểu Việt Nam (``3,52``),
  không đổi giá trị, chỉ đổi dấu phân cách.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Any

_DATE_RE = re.compile(r"^\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{2,4})\s*$")


def _strip_accents(text: str) -> str:
    # 'Đ' là chữ có nét gạch, NFD không tách được -> đổi tay để ánh xạ 1:1
    text = text.replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def norm_date(value: Any, dayfirst: bool = True) -> str:
    """Chuẩn hoá ngày về ``dd/mm/yyyy``.

    ``1/11/2026`` -> ``01/11/2026``; chấp nhận cả ``1-11-26``, ``2026-11-01``.
    Nếu không nhận dạng được thì trả lại nguyên văn (đã strip).
    """
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    text = str(value).strip()
    m = _DATE_RE.match(text)
    if m:
        a, b, y = m.groups()
        y = int(y)
        if y < 100:
            y += 2000
        if dayfirst:
            d, mo = int(a), int(b)
        else:  # yyyy-mm-dd
            d, mo = int(b), int(a)
        try:
            return date(y, mo, d).strftime("%d/%m/%Y")
        except ValueError:
            return text
    # dạng ISO 2026-11-01
    m = re.match(r"^\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\s*$", text)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        try:
            return date(y, mo, d).strftime("%d/%m/%Y")
        except ValueError:
            return text
    return text


def digits_only(value: Any) -> str:
    """Giữ lại chữ số (dùng cho số máy, số tem, số công tơ)."""
    if value is None:
        return ""
    return re.sub(r"\D", "", str(value))


def _fix_decimal_separator(num: str) -> str:
    """Đưa một chuỗi số về dạng thập phân bằng dấu phẩy."""
    num = num.strip()
    has_comma, has_dot = "," in num, "." in num
    if has_comma and has_dot:
        # dấu xuất hiện sau cùng là dấu thập phân
        if num.rfind(",") > num.rfind("."):
            num = num.replace(".", "").replace(",", ".")
        else:
            num = num.replace(",", "")
    elif has_comma:
        num = num.replace(",", ".")
    # giờ num chỉ còn dấu chấm làm dấu thập phân (nếu có)
    if "." in num:
        head, _, tail = num.partition(".")
        head = head or "0"
        num = f"{head}.{tail}"
    return num


def norm_number(value: Any) -> str:
    """Chuẩn hoá số đo về dạng Việt Nam (dấu phẩy thập phân).

    ``3.52`` -> ``3,52``; ``>5000`` -> ``>5000``; ``1,580`` -> ``1,58``.
    Không làm tròn, không thêm bớt chữ số có nghĩa.
    """
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        text = repr(value) if isinstance(value, float) else str(value)
        return _fix_decimal_separator(text).replace(".", ",")
    text = str(value).strip()
    if not text:
        return ""
    # tách phần so sánh đầu (> >= < <= ~) và đơn vị cuối
    m = re.match(r"^([<>≤≥~]*)\s*(.+?)\s*$", text)
    prefix, body = "", text
    if m:
        prefix, body = m.group(1), m.group(2)
    um = re.match(r"^(.*?)(\s*[A-Za-zΩµΩ%/]+.*)$", body)
    unit = ""
    if um and um.group(2).strip():
        body, unit = um.group(1), um.group(2)
    core = body.replace(" ", "").replace("\u00a0", "")
    if re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?", core):
        # 1.234 / 12.345.678 -> dấu phân cách nghìn (không phải thập phân)
        if re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+", core):
            return f"{prefix}{core}{unit}".strip()
        core = _fix_decimal_separator(core).replace(".", ",")
        return f"{prefix}{core}{unit}".strip()
    return f"{prefix}{body}{unit}".strip() if prefix or unit else text.strip()


def norm_text(value: Any) -> str:
    """Chuẩn hoá khoảng trắng thừa, bỏ gạch đầu dòng thừa."""
    if value is None:
        return ""
    text = str(value).replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


def norm_code(value: Any) -> str:
    """Chuẩn hoá 'mã' kiểu ``50441126/BB-TC``."""
    return norm_text(value).upper()


def flexible(text: str) -> str:
    """Khoá so khớp: không dấu, không hoa/thường, không khoảng trắng."""
    text = _strip_accents(norm_text(text)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def norm_device_voltage(value: Any) -> str:
    """Điện áp định mức: giữ dấu phẩy thập phân, thêm kV nếu thiếu."""
    text = norm_number(value)
    if not text:
        return ""
    if re.fullmatch(r"[<>]?\s*[\d,]+", text):
        return f"{text}kV"
    return text


def number_to_words_vi(n: int) -> str:
    """Đọc số nguyên dương thành chữ tiếng Việt (dùng cho 'Một (01) ...')."""
    if n < 0:
        return str(n)
    if n == 0:
        return "không"

    digits = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
    units = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"]

    def read_three(num: int) -> str:
        parts = []
        hundred, rem = divmod(num, 100)
        ten, one = divmod(rem, 10)
        if hundred:
            parts.append(f"{digits[hundred]} trăm")
        if ten == 0 and one and parts:
            parts.append("lẻ")
        if ten > 1:
            parts.append(f"{digits[ten]} mươi")
        elif ten == 1:
            parts.append("mười")
        if one:
            if one == 1 and ten > 1:
                parts.append("mốt")
            elif one == 5 and ten > 0:
                parts.append("lăm")
            elif one == 4 and ten > 1:
                parts.append("tư")
            else:
                parts.append(digits[one])
        return " ".join(parts)

    groups = []
    while n:
        n, r = divmod(n, 1000)
        groups.append(r)
    words = []
    for idx in range(len(groups) - 1, -1, -1):
        g = groups[idx]
        if g == 0:
            continue
        chunk = read_three(g)
        if units[idx]:
            chunk = f"{chunk} {units[idx]}"
        words.append(chunk)
    return " ".join(words)


def quantity_both(number: Any) -> str:
    """``1`` -> ``Một (01)``; ``01`` -> ``Một (01)`` (giữ 2 chữ số như mẫu)."""
    d = digits_only(number)
    if not d:
        return norm_text(number)
    n = int(d)
    return f"{number_to_words_vi(n).capitalize()} ({n:02d})"


def smart_title(text: str) -> str:
    """Viết hoa chữ đầu mỗi từ, giữ nguyên các từ đã in hoa (tên viết tắt)."""
    if not text:
        return ""

    def cap(word: str) -> str:
        if word.isupper():
            return word
        return word[:1].upper() + word[1:]

    keep = {"kVA", "kVA.", "kV", "MVA", "MCCB", "LA", "FCO", "MBA", "TBA"}
    out = []
    for w in text.split(" "):
        core = re.sub(r"[^\wÀ-ỹ]+$", "", w)
        if core in keep or (core and core[-1:].isdigit()):
            out.append(w)
        else:
            out.append(cap(w))
    return " ".join(out)
