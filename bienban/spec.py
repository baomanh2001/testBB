"""Đặc tả từng mẫu biên bản: nhãn nào lấy dữ liệu ở đâu.

Mỗi form là một danh sách **có thứ tự** các ô cần điền, đúng thứ tự trên
xuống / trái sang phải như trong file mẫu Word (nguyên tắc *Key Ordering*).
Nhờ vậy script không thể điền lệch ô, và khi mẫu thay đổi chỉ cần sửa file
này (hoặc ``config/labels.json``) mà không phải đụng vào code.

``style`` dùng để quyết định in đậm / in hoa:

* ``header``   – biến tiêu đề (Tên công trình, Địa chỉ, Kết luận): mặc định
  giữ đúng định dạng của mẫu, bật ``style.bold_header_values`` /
  ``style.upper_header_values`` trong cấu hình là đổi được.
* ``value``    – thông số đo: chữ thường, canh giữa ô.
* ``fixed``    – cụm cố định của mẫu (Tần số 50Hz, số pha...): giữ nguyên.
"""

from __future__ import annotations

TEMPLATES = {
    "44": "44 BB MBA 1P.docx",
    "45": "45 MCCB 250A.docx",
    "46": "46 BB LA.docx",
    "47": "47 BB FCO.docx",
    "48": "48 BB điện trở nối đất.docx",
    "49": "49 BB MBA 3P.docx",
    "93": "93 BB ACB.docx",
    "97": "97 BB cáp ngầm.docx",
}

# Khoá tương ứng trong JSON cho từng biên bản
DATA_KEYS = {
    "44": "bien_ban_44_mba",
    "45": "bien_ban_45_mccb",
    "46": "bien_ban_46_la",
    "47": "bien_ban_47_fco",
    "48": "bien_ban_48_tiep_dat",
    "49": "bien_ban_49_mba_3p",
    "93": "bien_ban_93_acb",
    "97": "bien_ban_97_cap_ngam",
}

TITLES = {
    "44": "MÁY BIẾN ÁP 1 PHA",
    "45": "MÁY CẮT HẠ THẾ (MCCB)",
    "46": "CHỐNG SÉT VAN (LA)",
    "47": "CẦU CHÌ TỰ RƠI (FCO)",
    "48": "ĐIỆN TRỞ NỐI ĐẤT",
    "49": "MÁY BIẾN ÁP 3 PHA",
    "93": "MÁY CẮT HẠ THẾ (ACB)",
    "97": "THÔNG TUYẾN CÁP NGẦM TRUNG THẾ",
}

DOC_KIND = {"44": "KIỂM ĐỊNH", "45": "KIỂM ĐỊNH", "46": "KIỂM ĐỊNH",
            "47": "KIỂM ĐỊNH", "48": "THỬ NGHIỆM", "49": "KIỂM ĐỊNH",
            "93": "THỬ NGHIỆM", "97": "KIỂM ĐỊNH"}

DEVICE_NOUN = {
    "44": "Máy biến áp 1 pha",
    "45": "máy cắt hạ thế (MCCB)",
    "46": "chống sét van",
    "47": "FCO",
    "48": "điện trở nối đất",
    "49": "máy biến áp 3 pha",
    "93": "máy cắt hạ thế (ACB)",
    "97": "đoạn cáp ngầm trung thế",
}

# --------------------------------------------------------------------------- #
# Thứ tự ô của từng mẫu
# --------------------------------------------------------------------------- #
LABELS: dict[str, list[dict]] = {
    "44": [
        # --- I. LÝ LỊCH THIẾT BỊ ---
        {"label": "Hiệu máy", "path": "hieu_may|hieu", "style": "value"},
        {"label": "Số tem", "path": "so_tem", "fmt": "code", "style": "value"},
        {"label": "Số máy", "path": "so_may", "fmt": "code", "style": "value"},
        {"label": "Năm sản xuất", "path": "nam_san_xuat", "fmt": "digits", "style": "value"},
        {"label": "Nước sản xuất", "path": "nuoc_san_xuat", "style": "value"},
        {"label": "Tần số", "path": "tan_so", "style": "value"},
        {"label": "Tên công trình", "path": "thong_tin_chung.ten_cong_trinh", "style": "header"},
        {"label": "Địa chỉ", "path": "thong_tin_chung.dia_chi", "style": "header"},
        {"label": "Đơn vị yêu cầu", "path": "thong_tin_chung.don_vi_yeu_cau", "style": "header"},
        {"label": "Lý do kiểm định", "path": "thong_tin_chung.ly_do_kiem_dinh", "style": "value"},
        {"label": "Nơi kiểm định", "path": "thong_tin_chung.noi_kiem_dinh", "style": "value"},
        {"label": "Ngày kiểm định", "path": "thong_tin_chung.ngay_kiem_dinh", "fmt": "date", "style": "value"},
        # --- II. QUY CÁCH KỸ THUẬT ---
        {"label": "Công suất định mức", "path": "cong_suat_dinh_muc", "style": "value"},
        {"label": "Điện áp định mức", "path": "dien_ap_dinh_muc", "style": "value"},
        {"label": "Số pha", "path": "so_pha", "fmt": "digits", "style": "value"},
        {"label": "Tổ đấu dây", "path": "to_dau_day", "style": "value"},
        # --- III. KẾT QUẢ KIỂM ĐỊNH ---
        {"label": "Kiểm tra bên ngoài", "path": "kiem_tra_ben_ngoai", "style": "value"},
        {"table": "insulation"},
        {"table": "r_dc"},
        {"table": "ratio"},
        {"table": "no_load"},
        {"table": "short_circuit"},
        {"table": "voltage_test"},
        {"label": "KẾT LUẬN", "path": "ket_luan", "style": "header"},
    ],
    "45": [
        {"label": "Tên công trình", "path": "thong_tin_chung.ten_cong_trinh", "style": "header"},
        {"label": "Địa chỉ", "path": "thong_tin_chung.dia_chi", "style": "header"},
        {"label": "Đơn vị yêu cầu", "path": "thong_tin_chung.don_vi_yeu_cau", "style": "header"},
        {"label": "Chỉ danh", "path": "chi_danh", "style": "value"},
        {"label": "Lý do kiểm định", "path": "thong_tin_chung.ly_do_kiem_dinh", "style": "value"},
        {"label": "Nơi kiểm định", "path": "thong_tin_chung.noi_kiem_dinh", "style": "value"},
        {"label": "Ngày kiểm định", "path": "thong_tin_chung.ngay_kiem_dinh", "fmt": "date", "style": "value"},
        {"label": "Hiệu", "path": "hieu", "style": "value"},
        {"label": "Số cực", "path": "so_cuc", "fmt": "digits", "style": "value"},
        {"label": "Loại", "path": "loai", "style": "value"},
        {"label": "Kiểu", "path": "kieu", "style": "value"},
        {"label": "Điện áp định mức", "path": "dien_ap_dinh_muc", "style": "value"},
        {"label": "Dòng điện định mức", "path": "dong_dinh_muc", "style": "value"},
        {"label": "Dòng điện ngắn mạch tối đa", "path": "dong_ngan_mach_toi_da", "style": "value"},
        {"label": "Tần số", "path": "tan_so", "style": "value"},
        {"label": "Điện áp cách điện định mức", "path": "dien_ap_cach_dien", "style": "value"},
        {"label": "Điện áp chịu xung định mức", "path": "dien_ap_xung", "style": "value"},
        {"label": "Kiểm tra bên ngoài", "path": "kiem_tra_ben_ngoai", "style": "value"},
        {"label": "Số lượng", "path": "so_luong", "fmt": "pad2", "style": "value"},
        {"table": "mccb"},
        {"label": "KẾT LUẬN", "path": "ket_luan", "style": "header"},
    ],
    "93": [
        {"label": "Tên công trình", "path": "thong_tin_chung.ten_cong_trinh", "style": "header"},
        {"label": "Địa chỉ", "path": "thong_tin_chung.dia_chi", "style": "header"},
        {"label": "Đơn vị yêu cầu", "path": "thong_tin_chung.don_vi_yeu_cau", "style": "header"},
        {"label": "Chỉ danh", "path": "chi_danh", "style": "value"},
        {"label": "Lý do thử nghiệm", "path": "thong_tin_chung.ly_do_kiem_dinh", "style": "value"},
        {"label": "Nơi thử nghiệm", "path": "thong_tin_chung.noi_kiem_dinh", "style": "value"},
        {"label": "Ngày thử nghiệm", "path": "thong_tin_chung.ngay_kiem_dinh", "fmt": "date", "style": "value"},
        {"label": "Hiệu", "path": "hieu", "style": "value"},
        {"label": "Số cực", "path": "so_cuc", "fmt": "digits", "style": "value"},
        {"label": "Loại", "path": "loai", "style": "value"},
        {"label": "Kiểu", "path": "kieu", "style": "value"},
        {"label": "Điện áp định mức", "path": "dien_ap_dinh_muc", "style": "value"},
        {"label": "Dòng điện định mức", "path": "dong_dinh_muc", "style": "value"},
        {"label": "Dòng điện ngắn mạch tối đa", "path": "dong_ngan_mach_toi_da", "style": "value"},
        {"label": "Tần số", "path": "tan_so", "style": "value"},
        {"label": "Điện áp cách điện định mức", "path": "dien_ap_cach_dien", "style": "value"},
        {"label": "Điện áp chịu xung định mức", "path": "dien_ap_xung", "style": "value"},
        {"label": "Kiểm tra bên ngoài", "path": "kiem_tra_ben_ngoai", "style": "value"},
        {"label": "Số lượng", "path": "so_luong", "fmt": "pad2", "style": "value"},
        {"table": "mccb"},
        {"label": "KẾT LUẬN", "path": "ket_luan", "style": "header"},
    ],
    "97": [
        {"label": "Tên công trình", "path": "thong_tin_chung.ten_cong_trinh", "style": "header"},
        {"label": "Địa chỉ", "path": "thong_tin_chung.dia_chi", "style": "header"},
        {"label": "Đơn vị yêu cầu", "path": "thong_tin_chung.don_vi_yeu_cau", "style": "header"},
        {"label": "Chỉ danh", "path": "chi_danh", "style": "value"},
        {"label": "Lý do kiểm định", "path": "thong_tin_chung.ly_do_kiem_dinh", "style": "value"},
        {"label": "Nơi kiểm định", "path": "thong_tin_chung.noi_kiem_dinh", "style": "value"},
        {"label": "Ngày kiểm định", "path": "thong_tin_chung.ngay_kiem_dinh", "fmt": "date", "style": "value"},
        {"label": "- Số tem", "path": "so_tem", "fmt": "digits", "style": "value"},
        {"label": "Đoạn cáp đi từ", "path": "doan_cap_tu", "style": "value"},
        {"label": "Đến", "path": "doan_cap_den", "style": "value"},
        {"label": "Loại cáp", "path": "loai_cap", "style": "value"},
        {"label": "Tiết diện", "path": "tiet_dien", "style": "value"},
        {"label": "Điện áp định mức", "path": "dien_ap_dinh_muc", "style": "value"},
        {"label": "Tần số", "path": "tan_so", "style": "value"},
        {"label": "Kiểm tra bên ngoài", "path": "kiem_tra_ben_ngoai", "style": "value"},
        {"label": "Nhiệt độ", "path": "nhiet_do", "style": "value"},
        {"table": "cap_ngam"},
        {"table": "cap_ngam_dc"},
        {"label": "KẾT LUẬN", "path": "ket_luan", "style": "header"},
    ],
    "46": [
        {"label": "Tên công trình", "path": "thong_tin_chung.ten_cong_trinh", "style": "header"},
        {"label": "Địa chỉ", "path": "thong_tin_chung.dia_chi", "style": "header"},
        {"label": "Đơn vị yêu cầu", "path": "thong_tin_chung.don_vi_yeu_cau", "style": "header"},
        {"label": "Chỉ danh", "path": "chi_danh", "style": "value"},
        {"label": "Lý do kiểm định", "path": "thong_tin_chung.ly_do_kiem_dinh", "style": "value"},
        {"label": "Nơi kiểm định", "path": "thong_tin_chung.noi_kiem_dinh", "style": "value"},
        {"label": "Ngày kiểm định", "path": "thong_tin_chung.ngay_kiem_dinh", "fmt": "date", "style": "value"},
        {"label": "Vật liệu cách điện", "path": "vat_lieu", "style": "value"},
        {"label": "MCOV", "path": "mcov", "style": "value"},
        {"label": "Điện áp định mức", "path": "dien_ap_dinh_muc", "style": "value"},
        {"label": "Tần số", "path": "tan_so", "style": "value"},
        {"label": "Dòng điện xả tối đa", "path": "dong_xa_toi_da", "style": "value"},
        {"label": "Kiểm tra bên ngoài", "path": "kiem_tra_ben_ngoai", "style": "value"},
        {"label": "Số lượng", "path": "so_luong", "fmt": "pad2", "style": "value"},
        {"table": "la"},
        {"label": "KẾT LUẬN", "path": "ket_luan", "style": "header"},
    ],
    "47": [
        {"label": "Tên công trình", "path": "thong_tin_chung.ten_cong_trinh", "style": "header"},
        {"label": "Địa chỉ", "path": "thong_tin_chung.dia_chi", "style": "header"},
        {"label": "Đơn vị yêu cầu", "path": "thong_tin_chung.don_vi_yeu_cau", "style": "header"},
        {"label": "Chỉ danh", "path": "chi_danh", "style": "value"},
        {"label": "Lý do kiểm định", "path": "thong_tin_chung.ly_do_kiem_dinh", "style": "value"},
        {"label": "Nơi kiểm định", "path": "thong_tin_chung.noi_kiem_dinh", "style": "value"},
        {"label": "Ngày kiểm định", "path": "thong_tin_chung.ngay_kiem_dinh", "fmt": "date", "style": "value"},
        {"label": "Vật liệu cách điện", "path": "vat_lieu", "style": "value"},
        {"label": "Dòng điện định mức", "path": "dong_dinh_muc", "style": "value"},
        {"label": "Điện áp định mức", "path": "dien_ap_dinh_muc", "style": "value"},
        {"label": "Khả năng cắt ngắn mạch", "path": "kha_nang_cat_ngan_mach", "style": "value"},
        {"label": "Kiểm tra bên ngoài", "path": "kiem_tra_ben_ngoai", "style": "value"},
        {"label": "Số lượng", "path": "so_luong", "fmt": "pad2", "style": "value"},
        {"table": "fco"},
        {"label": "KẾT LUẬN", "path": "ket_luan", "style": "header"},
    ],
    "48": [
        {"label": "Tên công trình", "path": "thong_tin_chung.ten_cong_trinh", "style": "header"},
        {"label": "Địa chỉ", "path": "thong_tin_chung.dia_chi", "style": "header"},
        {"label": "Chỉ danh", "path": "chi_danh", "style": "value"},
        {"label": "Đơn vị yêu cầu", "path": "thong_tin_chung.don_vi_yeu_cau", "style": "header"},
        {"label": "Lý do thử nghiệm", "path": "thong_tin_chung.ly_do_kiem_dinh|ly_do_thu_nghiem", "style": "value"},
        {"label": "Nơi thử nghiệm", "path": "thong_tin_chung.noi_kiem_dinh|noi_thu_nghiem", "style": "value"},
        {"label": "Ngày thử nghiệm", "path": "thong_tin_chung.ngay_kiem_dinh|ngay_thu_nghiem", "fmt": "date", "style": "value"},
        {"table": "earth"},
        {"label": "THIẾT BỊ THỬ NGHIỆM", "path": "thiet_bi_do", "style": "value"},
    ],
    # ---------------------------------------------------------------- 49 --
    # Chép đúng thứ tự ô trên bản in của ``092 BB MBA 1500kVA.doc``
    # (MBA 3 pha – Tổ đấu dây Dyn11). Khác mẫu 44 ở 4 bảng: cách điện
    # Cao–Vỏ/Cao–Hạ/Hạ–Vỏ, cuộn dây AB/BC/CA, tỉ số K1/K2/K3 và điện áp thử.
    "49": [
        # --- I. LÝ LỊCH THIẾT BỊ ---
        {"label": "Hiệu máy", "path": "hieu_may|hieu", "style": "value"},
        {"label": "Số tem", "path": "so_tem", "fmt": "code", "style": "value"},
        {"label": "Số máy", "path": "so_may", "fmt": "code", "style": "value"},
        {"label": "Năm sản xuất", "path": "nam_san_xuat", "fmt": "digits", "style": "value"},
        {"label": "Nước sản xuất", "path": "nuoc_san_xuat", "style": "value"},
        {"label": "Tên công trình", "path": "thong_tin_chung.ten_cong_trinh", "style": "header"},
        {"label": "Địa chỉ", "path": "thong_tin_chung.dia_chi", "style": "header"},
        {"label": "Đơn vị yêu cầu", "path": "thong_tin_chung.don_vi_yeu_cau", "style": "header"},
        {"label": "Lý do kiểm định", "path": "thong_tin_chung.ly_do_kiem_dinh", "style": "value"},
        {"label": "Nơi kiểm định", "path": "thong_tin_chung.noi_kiem_dinh", "style": "value"},
        {"label": "Ngày kiểm định", "path": "thong_tin_chung.ngay_kiem_dinh", "fmt": "date", "style": "value"},
        # --- II. QUY CÁCH KỸ THUẬT (Số pha 03 + Tổ đấu dây Dyn11) ---
        {"label": "Công suất định mức", "path": "cong_suat_dinh_muc", "style": "value"},
        {"label": "Số pha", "path": "so_pha", "fmt": "digits", "style": "value"},
        {"label": "Tần số", "path": "tan_so", "style": "value"},
        {"label": "Điện áp định mức", "path": "dien_ap_dinh_muc", "style": "value"},
        {"label": "Tổ đấu dây", "path": "to_dau_day", "style": "value"},
        # --- III. KẾT QUẢ KIỂM ĐỊNH ---
        {"label": "Kiểm tra bên ngoài", "path": "kiem_tra_ben_ngoai", "style": "value"},
        {"label": "Nhiệt độ", "path": "nhiet_do", "style": "value"},
        {"table": "insulation_3p"},
        {"table": "r_dc_3p"},
        {"table": "ratio_3p"},
        {"table": "no_load"},
        {"table": "short_circuit"},
        {"table": "voltage_test_3p"},
        {"label": "KẾT LUẬN", "path": "ket_luan", "style": "header"},
    ],
}

# Giá trị mặc định khi mẫu có ô nhưng dữ liệu không có (giữ đúng quy ước của
# công ty: để "-" thay vì bỏ trống).
EMPTY_PLACEHOLDER = "-"

# Các từ khoá nhận diện bảng trong từng mẫu (dùng để tìm đúng bảng).
# Mỗi bảng được nhận diện bằng một khoá "neo" (chuỗi đặc trưng chỉ bảng đó
# có) + số cột tối thiểu. Nhờ vậy bảng tỉ số biến áp và bảng R một chiều
# không bị nhận nhầm cho nhau.
TABLE_PROBES = {
    # Mẫu 44: bảng của MBA 1 pha (3 dòng "Cao+Vỏ – Hạ 1/Hạ 2", 11 cột "Hạ 1/Hạ 2")
    "insulation": (["R60", "R15", "Kht"], 4),
    "r_dc": (["Cuộn dây cao áp", "Cuộn dây hạ áp"], 8),
    "ratio": (["Hạ 1", "Hạ 2"], 10),
    # Mẫu 49: bảng của MBA 3 pha. Neo bằng chuỗi chỉ bản 3 pha mới có, nhờ vậy
    # bảng 1 pha không bao giờ bị nhận nhầm (và ngược lại).
    "insulation_3p": (["R60", "R15", "Kht", "Cao – Vỏ", "Cao – Hạ", "Hạ – Vỏ"], 4),
    # bảng 3 pha chỉ 5 cột: Nấc | AB | BC | CA | (hạ áp gộp 1 ô)
    "r_dc_3p": (["Cuộn dây cao áp", "Cuộn dây hạ áp", "AB", "BC", "CA"], 5),
    "ratio_3p": (["K1", "K2", "K3"], 4),
    "voltage_test_3p": (["Cao – (Hạ + vỏ)", "Hạ – (Cao + vỏ)"], 3),
    "cap_ngam": (["Tiêu chuẩn", "Số liệu đo", "Pha 1"], 3),
    "cap_ngam_dc": (["Thời gian", "Điện áp thử nghiệm", "Dòng rò"], 4),
    "no_load": (["U0", "I0", "P0"], 5),
    "short_circuit": (["UN", "PN75"], 5),
    "voltage_test": (["Đối tượng thử", "Thời gian thử"], 3),
    "mccb": (["R tiếp xúc", "Utest", "Số tem"], 10),
    "la": (["Dòng điện rò", "Điện áp AC"], 4),
    "fco": (["Trước khi thử cao áp", "Sau khi thử cao áp"], 7),
    "earth": (["kết nối với trung tính", "Loại tiếp đất", "Giá trị đo"], 5),
}

# Số dòng tiêu đề (header) của từng bảng – dữ liệu bắt đầu ngay sau đó.
TABLE_HEADER_ROWS = {
    "insulation": 1, "r_dc": 2, "ratio": 2, "no_load": 1, "short_circuit": 1,
    "voltage_test": 1, "mccb": 2, "la": 1, "fco": 2, "earth": 1,
    "insulation_3p": 1, "r_dc_3p": 2, "ratio_3p": 1, "voltage_test_3p": 1,
}

# --------------------------------------------------------------------------- #
# Giải mã SỐ BIÊN BẢN: 50 | <mã văn bản> | <tháng> | <năm>
# --------------------------------------------------------------------------- #
#: Mã văn bản đi kèm từng mẫu (2 chữ số cuối của số hiệu in trên tờ).
#: VD biên bản MBA 3 pha: ``50|92|10|26`` → ``50921026/BB-TC``.
FORM_DOC_CODE = {
    "44": "44",
    "45": "45",
    "46": "46",
    "47": "47",
    "48": "48",
    "49": "92",
    "93": "93",
    "94": "94",
    "95": "95",
    "96": "96",
    "97": "97",
    "109": "09",
}


def decode_doc_no(so: str) -> dict:
    """Bóc số biên bản thành các phần: mã văn bản, tháng, năm của phiên.

    ``"50921026/BB-TC"`` → ``{"ok": True, "code": "92", "thang": 10, "nam": 2026,
    "phien": "tháng 10/2026"}``.

    Định dạng công ty: **50** + mã văn bản (2 số) + tháng (2 số) + năm (2 số).
    Nhờ vậy biết ngay một tờ là **phiên cũ hay phiên mới** mà không cần đoán.
    """
    digits = "".join(ch for ch in str(so or "") if ch.isdigit())
    if len(digits) != 8 or not digits.startswith("50"):
        return {"ok": False, "raw": str(so or "")}
    code, thang, nam = digits[2:4], digits[4:6], digits[6:8]
    if not (1 <= int(thang) <= 12):
        return {"ok": False, "raw": str(so or "")}
    return {
        "ok": True,
        "prefix": digits[:2],
        "code": code,
        "thang": int(thang),
        "nam": 2000 + int(nam),
        "phien": f"tháng {int(thang):02d}/{2000 + int(nam)}",
    }


def expected_doc_no(form: str, ngay: str) -> str:
    """Số hiệu đúng phải có, suy từ mẫu + ngày kiểm định (``dd/mm/yyyy``)."""
    import re as _re

    m = _re.match(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\s*$", str(ngay or ""))
    code = FORM_DOC_CODE.get(str(form))
    if not m or not code:
        return ""
    return f"50{code}{int(m.group(2)):02d}{m.group(3)[2:]}/BB-TC"
