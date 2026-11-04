"""Kiểm tra JSON trước khi điền form.

Mục tiêu: phát hiện sớm lỗi thường gặp của bước trích xuất ảnh (OCR/LLM) —
sai định dạng ngày, dấu thập phân kiểu Mỹ, thiếu số máy/số tem, thiếu dãy số
liệu 5 nấc.

**Ô trống chỉ là cảnh báo, không chặn in.** Người dùng cố ý để trống (in bản
nháp, bổ sung tay sau khi in) nên tool vẫn sinh Word bình thường; ô trống in ra
dấu ``-``. Chỉ hai trường hợp mới là lỗi chặn in:

* JSON gốc không phải object;
* không có khối biên bản nào (``bien_ban_44..48``) để in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .normalize import digits_only, norm_date
from .spec import FORM_DOC_CODE, decode_doc_no, expected_doc_no


@dataclass
class Problem:
    level: str      # "error" | "warn"
    where: str
    message: str
    #: True = chặn sinh biên bản; False (mặc định) = chỉ cảnh báo cho người dùng.
    #: Ô trống không bao giờ chặn: in ra "-" và vẫn cho xem trước Word.
    blocking: bool = False


DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
FORM_KEYS = [
    ("44", "bien_ban_44_mba"),
    ("45", "bien_ban_45_mccb"),
    ("46", "bien_ban_46_la"),
    ("47", "bien_ban_47_fco"),
    ("48", "bien_ban_48_tiep_dat"),
    ("49", "bien_ban_49_mba_3p"),
]

REQUIRED_COMMON = [
    "ten_cong_trinh",
    "dia_chi",
    "don_vi_yeu_cau",
    "ly_do_kiem_dinh",
    "noi_kiem_dinh",
    "ngay_kiem_dinh",
]

# (khoá, bắt buộc?, mô tả)
REQUIRED_FIELDS = {
    "44": [
        ("so_bien_ban", True, "Số biên bản"),
        ("so_may", True, "Số máy"),
        ("so_tem", True, "Số tem"),
        ("cong_suat_dinh_muc", True, "Công suất định mức"),
        ("dien_ap_dinh_muc", True, "Điện áp định mức"),
        ("r_cach_dien_Mohm", True, "Điện trở cách điện"),
        ("r_cuon_day_1_chieu_ohm", True, "R một chiều cuộn dây"),
        ("ti_so_bien_ap", True, "Tỉ số biến áp"),
        ("khong_tai", True, "Thí nghiệm không tải"),
        ("ngan_mach", True, "Thí nghiệm ngắn mạch"),
        ("ket_luan", False, "Kết luận"),
    ],
    "45": [
        ("so_bien_ban", True, "Số biên bản"),
        ("hieu", True, "Hiệu MCCB"),
        ("kieu", True, "Kiểu MCCB"),
        ("dong_dinh_muc", True, "Dòng định mức"),
        ("so_tem", True, "Số tem"),
        ("r_cach_dien_Mohm", True, "R cách điện"),
        ("r_tiep_xuc_uohm", True, "R tiếp xúc"),
    ],
    "46": [
        ("so_bien_ban", True, "Số biên bản"),
        # Chỉ danh để trống được: bộ điền tự ghép "LA <U>-<I xả>" (derive_values)
        ("chi_danh", False, "Chỉ danh LA"),
        ("vat_lieu", True, "Vật liệu cách điện"),
        ("dien_ap_dinh_muc", True, "Điện áp định mức"),
        ("mcov", True, "MCOV"),
        ("dong_xa_toi_da", True, "Dòng xả tối đa"),
    ],
    "47": [
        ("so_bien_ban", True, "Số biên bản"),
        # Chỉ danh để trống được: bộ điền tự ghép "FCO – <dòng định mức>"
        ("chi_danh", False, "Chỉ danh FCO"),
        ("vat_lieu", True, "Vật liệu cách điện"),
        ("dien_ap_dinh_muc", True, "Điện áp định mức"),
        ("dong_dinh_muc", True, "Dòng định mức"),
        ("kha_nang_cat_ngan_mach", True, "Khả năng cắt ngắn mạch"),
    ],
    "48": [
        ("so_bien_ban", True, "Số biên bản"),
        ("chi_danh", True, "Chỉ danh"),
        ("ket_noi_trung_tinh", True, "Kết nối trung tính"),
        ("loai_tiep_dat", True, "Loại tiếp đất"),
        ("gia_tri_do_Ohm", True, "Giá trị đo"),
        ("thiet_bi_do", True, "Thiết bị đo"),
    ],
    "49": [
        ("hieu_may", True, "Hiệu máy"),
        ("so_may", True, "Số máy"),
        ("cong_suat_dinh_muc", True, "Công suất định mức"),
        ("dien_ap_dinh_muc", True, "Điện áp định mức"),
        ("to_dau_day", True, "Tổ đấu dây"),
        ("so_bien_ban", True, "Số biên bản"),
    ],
}


def _check_date(value, where: str, problems: list[Problem], *, required=True):
    if not value:
        if required:
            problems.append(Problem("warn", where, "Thiếu ngày – sẽ in dấu “-”"))
        return
    normalized = norm_date(value)
    valid = bool(DATE_RE.match(normalized))
    if valid:
        d, mo, y = (int(x) for x in normalized.split("/"))
        try:
            date(y, mo, d)
        except ValueError:
            valid = False
    if not valid:
        problems.append(Problem("warn", where,
                                f"Ngày không hợp lệ: {value!r} – sẽ giữ nguyên chữ đã nhập"))
    elif normalized != str(value).strip():
        problems.append(
            Problem("warn", where, f"Ngày sẽ được chuẩn hoá: {value!r} → {normalized!r}")
        )


def _check_code(value, where: str, problems: list[Problem], length: int = 8):
    if not value:
        problems.append(Problem("warn", where, "Thiếu giá trị – sẽ in dấu “-”"))
        return
    d = digits_only(value)
    if len(d) != length:
        problems.append(
            Problem("warn", where, f"'{value}' chỉ có {len(d)} chữ số (mong đợi {length})")
        )


def _check_series(values, where: str, problems: list[Problem], expect: int = 5):
    if not isinstance(values, list):
        problems.append(Problem("warn", where, "Phải là danh sách số – sẽ in dấu “-”"))
        return
    if len(values) != expect:
        problems.append(
            Problem("warn", where, f"Có {len(values)} giá trị, mẫu cần {expect} nấc")
        )
    for v in values:
        if isinstance(v, str) and "." in v and "," not in v:
            problems.append(
                Problem("warn", where, f"Dấu thập phân kiểu Mỹ {v!r} → sẽ đổi thành dấu phẩy")
            )


# --------------------------------------------------------------------------- #
# Dạng dữ liệu mới: bảng là ``{"rows": [...]}``
# --------------------------------------------------------------------------- #
def _rows(value) -> list[dict] | None:
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        return [r for r in value["rows"] if isinstance(r, dict)]
    if isinstance(value, list) and value and all(isinstance(r, dict) for r in value):
        return value
    return None


def _row_field_problem(block: dict, field: str, value, label: str,
                       problems: list[Problem], where: str) -> bool:
    """True nếu ``field`` đã được thoả bởi ít nhất 1 dòng của bảng."""
    rows = _rows(block.get("rows"))
    if not rows:
        return False
    key = {
        "r_cach_dien_Mohm": "rcd_close", "r_tiep_xuc_uohm": "rtx_a",
        "so_tem": "so_tem", "chi_danh": "chi_danh", "gia_tri_do_Ohm": "gia_tri_do",
        "loai_tiep_dat": "loai_tiep_dat", "ket_noi_trung_tinh": "ket_noi_trung_tinh",
        "thiet_bi_do": "thiet_bi_do",
    }.get(field, field)
    if any((r.get(key) or "").strip() for r in rows):
        problems.append(Problem("warn", where, f"Lấy {label} từ bảng kết quả thay vì ô riêng"))
        return True
    return False


def validate(data: dict) -> list[Problem]:
    problems: list[Problem] = []
    if not isinstance(data, dict):
        return [Problem("error", "$", "JSON gốc phải là object", blocking=True)]

    tt = data.get("thong_tin_chung") or {}
    if not tt:
        problems.append(Problem("warn", "thong_tin_chung",
                                "Thiếu khối thông tin chung – các ô sẽ in dấu “-”"))
    for key in REQUIRED_COMMON:
        if not (tt.get(key) or "").strip():
            problems.append(Problem("warn", f"thong_tin_chung.{key}",
                                    "Thiếu giá trị – sẽ in dấu “-”, bổ sung sau cũng được"))
    _check_date(tt.get("ngay_kiem_dinh"), "thong_tin_chung.ngay_kiem_dinh", problems)
    _check_date(
        tt.get("ngay_lap_bien_ban"), "thong_tin_chung.ngay_lap_bien_ban", problems,
        required=False,
    )
    crew = tt.get("can_bo_ky_ten") or {}
    for k, label in [("nguoi_thu", "Người thử"), ("nguoi_kiem_tra", "Người kiểm tra")]:
        if not (crew.get(k) or "").strip():
            problems.append(Problem("warn", f"can_bo_ky_ten.{k}", f"Thiếu {label}"))

    found_any = False
    for form, key in FORM_KEYS:
        block = data.get(key)
        if block is None:
            problems.append(Problem("warn", key, "Không có dữ liệu – sẽ bỏ qua biên bản này"))
            continue
        found_any = True
        for field, required, label in REQUIRED_FIELDS[form]:
            value = block.get(field)
            if value in (None, "", [], {}):
                if required:
                    where = f"{key}.{field}"
                    if _row_field_problem(block, field, value, label, problems, where):
                        continue
                    problems.append(Problem("warn", where,
                                            f"Thiếu {label} – sẽ in dấu “-”"))
                continue
        if form in ("45", "46", "47") and not (block.get("chi_danh") or "").strip():
            if not _rows(block.get("rows")):
                problems.append(Problem(
                    "warn", f"{key}.chi_danh",
                    "Để trống – sẽ tự ghép từ hiệu/loại + dòng định mức"))
        if "so_bien_ban" in block:
            so = str(block["so_bien_ban"])
            if not re.search(r"/BB-", so):
                problems.append(
                    Problem("warn", f"{key}.so_bien_ban", f"Số '{so}' thiếu hậu tố '/BB-TC'")
                )
            # --- phiên cũ hay phiên mới? -----------------------------------
            # Số hiệu = 50 | mã văn bản | tháng | năm. Đối chiếu với ngày
            # kiểm định để phát hiện tờ bị trộn từ đợt khác.
            info = decode_doc_no(so)
            ngay = str(tt.get("ngay_kiem_dinh") or "").strip()
            if info.get("ok") and ngay:
                want = expected_doc_no(form, ngay)
                if want and so.split("/")[0].strip() != want.split("/")[0].strip():
                    problems.append(Problem(
                        "warn", f"{key}.so_bien_ban",
                        f"Số {so} là phiên {info['phien']}, nhưng ngày kiểm định "
                        f"{ngay} → đúng ra phải là {want}. Có thể tờ này thuộc "
                        f"đợt khác (cùng mẫu nhưng khác ngày)."))
                elif info.get("code") and info["code"] != FORM_DOC_CODE.get(form):
                    problems.append(Problem(
                        "warn", f"{key}.so_bien_ban",
                        f"Mã văn bản trong số hiệu là {info['code']}, không phải "
                        f"{FORM_DOC_CODE.get(form)} của mẫu {form}."))
        if form == "44":
            if block.get("so_may"):
                _check_code(block["so_may"], f"{key}.so_may", problems)
            if block.get("so_tem"):
                _check_code(block["so_tem"], f"{key}.so_tem", problems, length=6)
            if isinstance(block.get("r_cuon_day_1_chieu_ohm"), dict):
                rdc = block["r_cuon_day_1_chieu_ohm"]
                _check_series(rdc.get("cao_ap"), f"{key}.r_cuon_day_1_chieu_ohm.cao_ap", problems)
                _check_series(
                    rdc.get("ha_ap_mOhm"), f"{key}.r_cuon_day_1_chieu_ohm.ha_ap_mOhm",
                    problems, expect=2,
                )
            if isinstance(block.get("ti_so_bien_ap"), dict):
                tsb = block["ti_so_bien_ap"]
                _check_series(tsb.get("ha_1"), f"{key}.ti_so_bien_ap.ha_1", problems)
                _check_series(tsb.get("ha_2"), f"{key}.ti_so_bien_ap.ha_2", problems)
            for tbl in ("cao_vo_ha1", "cao_vo_ha2", "ha1_ha2"):
                item = (block.get("r_cach_dien_Mohm") or {}).get(tbl) or {}
                for f in ("r60", "r15", "knt"):
                    if item.get(f) in (None, ""):
                        problems.append(
                            Problem(
                                "warn",
                                f"{key}.r_cach_dien_Mohm.{tbl}.{f}",
                                "Thiếu số liệu điện trở cách điện – sẽ in dấu “-”",
                            )
                        )
        # --- MBA 3 pha: Số pha phải là 03 (hoặc bội của 3) ---
        if form == "49":
            so_pha = digits_only(block.get("so_pha") or "")
            if so_pha and so_pha not in ("03", "3", "003"):
                problems.append(Problem(
                    "warn", f"{key}.so_pha",
                    f"Mẫu 49 là máy biến áp 3 pha nhưng Số pha = {so_pha}"))
            to_dau = str(block.get("to_dau_day") or "").strip()
            if to_dau and not re.match(r"^(D|Y|YN|Dyn|Yyn|Yd|Dy|Dz|Yz)", to_dau, re.I):
                problems.append(Problem(
                    "warn", f"{key}.to_dau_day",
                    f"Tổ đấu dây {to_dau!r} không giống quy ước (Dyn11, Yyn0…)"))
        if form == "45" and block.get("so_tem"):
            _check_code(block["so_tem"], f"{key}.so_tem", problems, length=6)
        if form == "48" and block.get("gia_tri_do_Ohm") is not None:
            val = str(block["gia_tri_do_Ohm"])
            if "," not in val and "." in val:
                problems.append(
                    Problem("warn", f"{key}.gia_tri_do_Ohm",
                            f"{val!r} sẽ được ghi thành {val.replace('.', ',')}")
                )

    # --- Chặn in sai mẫu: Số pha không khớp mẫu biên bản ---
    b44 = data.get("bien_ban_44_mba")
    if isinstance(b44, dict):
        so_pha = digits_only(b44.get("so_pha") or "")
        if so_pha and so_pha not in ("01", "1", "001"):
            problems.append(Problem(
                "error", "bien_ban_44_mba.so_pha",
                f"Mẫu 44 là MÁY BIẾN ÁP 1 PHA nhưng Số pha = {so_pha}. "
                "Hãy dùng mẫu 49 (MBA 3 PHA) cho máy 3 pha.",
                blocking=True))
    b49 = data.get("bien_ban_49_mba_3p")
    if isinstance(b49, dict):
        so_pha = digits_only(b49.get("so_pha") or "")
        if so_pha and so_pha in ("01", "1", "001"):
            problems.append(Problem(
                "error", "bien_ban_49_mba_3p.so_pha",
                "Mẫu 49 là MÁY BIẾN ÁP 3 PHA nhưng Số pha = 01. "
                "Hãy dùng mẫu 44 (MBA 1 PHA).",
                blocking=True))

    if not found_any:
        problems.append(Problem("error", "$", "Không có khối bien_ban_44..48 nào",
                                blocking=True))
    return problems
