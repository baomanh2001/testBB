"""Đặc tả các ô **sửa được** trên giao diện — nguồn duy nhất cho web và AI.

Mỗi biên bản được mô tả bằng danh sách *nhóm* (group). Một nhóm hoặc chứa các
ô đơn (``fields``), hoặc chứa một bảng gồm nhiều dòng (``table``). Thứ tự nhóm
và thứ tự ô **trùng đúng thứ tự trên bản in**, nên người dùng đọc form trên màn
hình là đọc được bản Word sẽ in ra.

Cùng một file này được dùng cho 3 việc:

1. **Sinh form chỉnh sửa** trên web (mọi ô đều có input → sửa được khi AI đọc
   sai, xem :mod:`bienban.vision`);
2. **Sinh prompt** gửi Gemini: liệt kê đúng tên khoá + nhãn tiếng Việt + đơn vị
   + ví dụ, nên AI không thể trả về khoá lạ;
3. **Sinh cột bảng** khi thêm dòng, và kiểm tra dữ liệu.

Quy ước ``type``:

* ``text`` / ``textarea`` – chữ tự do (giữ nguyên dấu tiếng Việt)
* ``code``   – số máy / số tem: chỉ giữ chữ số
* ``date``   – ngày, xuất ra ``dd/mm/yyyy``
* ``number`` – số đo, dùng dấu phẩy thập phân, giữ dấu ``>`` / ``<``
* ``series`` – dãy số cố định (5 nấc, 2 cuộn…) – ``len`` cho biết số phần tử
* ``select`` – chọn trong ``options`` (vẫn gõ được giá trị khác)
"""

from __future__ import annotations

import json

from .spec import TEMPLATES, TITLES

# --------------------------------------------------------------------------- #
# Thông tin chung – dùng cho cả 5 biên bản
# --------------------------------------------------------------------------- #
COMMON_GROUP = {
    "title": "Thông tin chung (áp dụng cho mọi biên bản)",
    "fields": [
        # Thứ tự BÁM ĐÚNG thứ tự in: Số biên bản (SỐ: …) và Ngày lập (NGÀY: …)
        # nằm ở khối tiêu đề, trước Tên công trình.
        {"key": "so_bien_ban", "label": "Số biên bản", "type": "text",
         "hint": "VD: 50451126/BB-TC — in ở dòng “SỐ:” trên tiêu đề",
         "part": "header", "path": ["__so_bien_ban__"]},
        {"key": "ngay_lap_bien_ban", "label": "Ngày lập biên bản", "type": "date",
         "hint": "In ở dòng “NGÀY:” trên tiêu đề",
         "part": "header", "path": ["thong_tin_chung", "ngay_lap_bien_ban"]},
        {"key": "ten_cong_trinh", "label": "Tên công trình", "type": "text",
         "hint": "VD: Trạm biến áp 50kVA – DOANH NGHIỆP TƯ NHÂN E-GREEN",
         "path": ["thong_tin_chung", "ten_cong_trinh"]},
        {"key": "dia_chi", "label": "Địa chỉ", "type": "text",
         "path": ["thong_tin_chung", "dia_chi"]},
        {"key": "chi_danh", "label": "Chỉ danh", "type": "text",
         "hint": "VD: MCCB 250A / LA 18kV-10kA / FCO – 100A. Để trống = ghép tự động",
         "part": "project", "only": ["45", "46", "47"],
         "path": ["__block_field__", "chi_danh"]},
        {"key": "don_vi_yeu_cau", "label": "Đơn vị yêu cầu", "type": "text",
         "path": ["thong_tin_chung", "don_vi_yeu_cau"]},
        {"key": "ly_do_kiem_dinh", "label": "Lý do kiểm định", "type": "select",
         "options": ["Sau sự cố", "Định kỳ", "Lắp đặt mới", "Hiện trường"],
         "path": ["thong_tin_chung", "ly_do_kiem_dinh"]},
        {"key": "noi_kiem_dinh", "label": "Nơi kiểm định", "type": "select",
         "options": ["Tại hiện trường", "Tại phòng thí nghiệm"],
         "path": ["thong_tin_chung", "noi_kiem_dinh"]},
        {"key": "ngay_kiem_dinh", "label": "Ngày kiểm định", "type": "date",
         "path": ["thong_tin_chung", "ngay_kiem_dinh"]},
        {"key": "nguoi_thu", "part": "signature", "label": "Người thử (ký tên)", "type": "text",
         "path": ["thong_tin_chung", "can_bo_ky_ten", "nguoi_thu"]},
        {"key": "nguoi_kiem_tra", "part": "signature", "label": "Người kiểm tra (ký tên)", "type": "text",
         "path": ["thong_tin_chung", "can_bo_ky_ten", "nguoi_kiem_tra"]},
        {"key": "p_giam_doc", "part": "signature", "label": "P. Giám đốc (ký tên)", "type": "text",
         "path": ["thong_tin_chung", "can_bo_ky_ten", "p_giam_doc"]},
    ],
}

# Giá trị hay dùng – gợi ý trong ô chọn (vẫn cho gõ khác)
_KET_QUA = ["Đạt", "Không đạt"]
_NGOAI = ["Bình thường", "Không bình thường"]


def _num(key, label, unit="", hint="", **kw):
    d = {"key": key, "label": label, "type": "number", "unit": unit, "hint": hint}
    d.update(kw)
    return d


def _txt(key, label, hint="", **kw):
    d = {"key": key, "label": label, "type": "text", "hint": hint}
    d.update(kw)
    return d


def _series(key, label, n, unit="", hint="", item_labels=None):
    return {"key": key, "label": label, "type": "series", "len": n,
            "unit": unit, "itemLabels": item_labels or [f"nấc {i + 1}" for i in range(n)],
            "hint": hint}


FORM_GROUPS: dict[str, list[dict]] = {
    # ------------------------------------------------------------------ 44 --
    "44": [
        {"title": "I. Lý lịch máy biến áp", "position": "before_common", "fields": [
            _txt("hieu_may", "Hiệu máy", "VD: EMC"),
            _txt("so_tem", "Số tem", "6 chữ số in trên tem kiểm định", type="code"),
            _txt("so_may", "Số máy", "8 chữ số", type="code"),
            _txt("nam_san_xuat", "Năm sản xuất", "VD: 2004", type="code"),
            _txt("nuoc_san_xuat", "Nước sản xuất", "VD: Việt Nam",
                 **{"type": "select", "options": ["Việt Nam", "Trung Quốc", "Hàn Quốc",
                                                 "Nhật Bản", "Đài Loan", "Thái Lan"]}),
            _num("tan_so", "Tần số", "Hz", "VD: 50Hz"),
        ]},
        {"title": "II. Quy cách kỹ thuật", "fields": [
            _num("cong_suat_dinh_muc", "Công suất định mức", "kVA", "VD: 50kVA"),
            _txt("so_pha", "Số pha", "VD: 01", type="code"),
            _num("dien_ap_dinh_muc", "Điện áp định mức", "kV", "VD: 22/0,4kV"),
            _txt("to_dau_day", "Tổ đấu dây", "VD: I/I0"),
            _txt("kiem_tra_ben_ngoai", "Kiểm tra bên ngoài", "", type="select",
                 options=_NGOAI),
        ]},
        {"title": "1. Điện trở cách điện (MΩ) – 3 dòng cố định", "table": {
            "kind": "fixed", "key": "r_cach_dien_Mohm", "stt": False,
            "columns": [
                {"key": "r60", "label": "R60″ (MΩ)", "type": "number"},
                {"key": "r15", "label": "R15″ (MΩ)", "type": "number"},
                {"key": "knt", "label": "Kht = R60/R15", "type": "number"},
            ],
            "rows": [
                {"key": "cao_vo_ha1", "label": "(Cao+Vỏ) – Hạ 1"},
                {"key": "cao_vo_ha2", "label": "(Cao+Vỏ) – Hạ 2"},
                {"key": "ha1_ha2", "label": "Hạ 1 – Hạ 2"},
            ],
        }},
        {"title": "2. Điện trở một chiều cuộn dây", "fields": [
            _series("r_cuon_day_1_chieu_ohm.cao_ap", "Cuộn dây cao áp (Ω) – 5 nấc", 5, "Ω"),
            _series("r_cuon_day_1_chieu_ohm.ha_ap_mOhm", "Cuộn dây hạ áp (mΩ)", 2, "mΩ",
                    item_labels=["HA 1", "HA 2"]),
        ]},
        {"title": "3. Tỉ số biến áp – 5 nấc mỗi bên", "fields": [
            _series("ti_so_bien_ap.ha_1", "Tỉ số – Hạ 1", 5),
            _series("ti_so_bien_ap.ha_2", "Tỉ số – Hạ 2", 5),
        ]},
        {"title": "4. Thí nghiệm không tải", "fields": [
            _num("khong_tai.u0_V", "U0", "V"),
            _num("khong_tai.i0_A", "I0", "A"),
            _num("khong_tai.i0_pct", "I0%", "%"),
            _num("khong_tai.p0_W", "P0", "W"),
        ]},
        {"title": "5. Thí nghiệm ngắn mạch", "fields": [
            _num("ngan_mach.uk_V", "UN", "V"),
            _num("ngan_mach.uk_pct", "UN%", "%"),
            _num("ngan_mach.ik_A", "IN", "A"),
            _num("ngan_mach.pk_W", "PN75", "W"),
        ]},
        {"title": "6. Thử điện áp tăng cao", "fields": [
            _num("thu_dien_ap_tang_cao.cao_ap", "Cuộn dây cao áp", "kV"),
            _num("thu_dien_ap_tang_cao.ha_ap", "Cuộn dây hạ áp", "kV"),
            _txt("thu_dien_ap_tang_cao.thoi_gian", "Thời gian thử", "VD: 1 phút"),
        ]},
        {"title": "Kết luận", "fields": [
            {"key": "ket_luan", "label": "Kết luận", "type": "textarea",
             "hint": "Để trống = tool tự sinh câu kết luận chuẩn"},
        ]},
    ],
    # ------------------------------------------------------------------ 49 --
    # MBA 3 PHA – dựng theo bản in ``092 BB MBA 1500kVA.doc``. Khác 44 ở 4 bảng:
    # cách điện Cao–Vỏ/Cao–Hạ/Hạ–Vỏ, cuộn dây AB/BC/CA, tỉ số K1/K2/K3,
    # và điện áp thử Cao–(Hạ+vỏ) / Hạ–(Cao+vỏ).
    "49": [
        {"title": "I. Lý lịch máy biến áp 3 pha", "position": "before_common", "fields": [
            _txt("hieu_may", "Hiệu máy", "VD: THIBIDI"),
            _txt("so_tem", "Số tem", "6 chữ số in trên tem kiểm định", type="code"),
            _txt("so_may", "Số máy", "VD: 103150017", type="code"),
            _txt("nam_san_xuat", "Năm sản xuất", "VD: 2010", type="code"),
            _txt("nuoc_san_xuat", "Nước sản xuất", "VD: Việt Nam",
                 **{"type": "select", "options": ["Việt Nam", "Trung Quốc", "Hàn Quốc",
                                                 "Nhật Bản", "Đài Loan", "Thái Lan"]}),
        ]},
        {"title": "II. Quy cách kỹ thuật", "fields": [
            _num("cong_suat_dinh_muc", "Công suất định mức", "kVA", "VD: 1500kVA"),
            _txt("so_pha", "Số pha", "VD: 03", type="code"),
            _num("tan_so", "Tần số", "Hz", "VD: 50 Hz"),
            _num("dien_ap_dinh_muc", "Điện áp định mức", "kV", "VD: 22/0.4kV"),
            _txt("to_dau_day", "Tổ đấu dây", "VD: Dyn11"),
            _num("nhiet_do", "Nhiệt độ khi đo", "°C", "VD: 34"),
            _txt("kiem_tra_ben_ngoai", "Kiểm tra bên ngoài", "", type="select",
                 options=_NGOAI),
        ]},
        {"title": "1. Điện trở cách điện (MΩ) – 3 dòng của MBA 3 pha", "table": {
            "kind": "fixed", "key": "r_cach_dien_Mohm", "stt": False,
            "columns": [
                {"key": "r60", "label": "R60″ (MΩ)", "type": "number"},
                {"key": "r15", "label": "R15″ (MΩ)", "type": "number"},
                {"key": "knt", "label": "Kht = R60/R15", "type": "number"},
            ],
            "rows": [
                {"key": "cao_vo", "label": "Cao – Vỏ"},
                {"key": "cao_ha", "label": "Cao – Hạ"},
                {"key": "ha_vo", "label": "Hạ – Vỏ"},
            ],
        }},
        {"title": "2. Điện trở một chiều cuộn dây cao áp (Ω) – 5 nấc × AB/BC/CA",
         "fields": [
            _series("r_cuon_day_1_chieu_ohm.cao_ap.ab", "Cuộn cao áp AB (Ω)", 5, "Ω",
                    item_labels=[f"Nấc {i}" for i in range(1, 6)]),
            _series("r_cuon_day_1_chieu_ohm.cao_ap.bc", "Cuộn cao áp BC (Ω)", 5, "Ω",
                    item_labels=[f"Nấc {i}" for i in range(1, 6)]),
            _series("r_cuon_day_1_chieu_ohm.cao_ap.ca", "Cuộn cao áp CA (Ω)", 5, "Ω",
                    item_labels=[f"Nấc {i}" for i in range(1, 6)]),
        ]},
        {"title": "2b. Điện trở cuộn dây hạ áp (mΩ) – an / bn / cn", "fields": [
            _num("r_cuon_day_1_chieu_ohm.ha_ap_mOhm.an", "Hạ áp – an", "mΩ"),
            _num("r_cuon_day_1_chieu_ohm.ha_ap_mOhm.bn", "Hạ áp – bn", "mΩ"),
            _num("r_cuon_day_1_chieu_ohm.ha_ap_mOhm.cn", "Hạ áp – cn", "mΩ"),
        ]},
        {"title": "3. Tỉ số biến áp – K1 / K2 / K3 (5 nấc)", "fields": [
            _series("ti_so_bien_ap.k1", "Tỉ số K1", 5,
                    item_labels=[f"Nấc {i}" for i in range(1, 6)]),
            _series("ti_so_bien_ap.k2", "Tỉ số K2", 5,
                    item_labels=[f"Nấc {i}" for i in range(1, 6)]),
            _series("ti_so_bien_ap.k3", "Tỉ số K3", 5,
                    item_labels=[f"Nấc {i}" for i in range(1, 6)]),
        ]},
        {"title": "4. Thí nghiệm không tải", "fields": [
            _num("khong_tai.u0_V", "U0", "V"),
            _num("khong_tai.i0_A", "I0", "A"),
            _num("khong_tai.i0_pct", "I0%", "%"),
            _num("khong_tai.p0_W", "P0", "W"),
        ]},
        {"title": "5. Thí nghiệm ngắn mạch", "fields": [
            _num("ngan_mach.uk_V", "UN", "V"),
            _num("ngan_mach.uk_pct", "UN%", "%"),
            _num("ngan_mach.ik_A", "IN", "A"),
            _num("ngan_mach.pk_W", "PN75", "W"),
        ]},
        {"title": "6. Thử điện áp tăng cao (MBA 3 pha)", "fields": [
            _num("thu_dien_ap_tang_cao.cao_vo", "Cao – (Hạ + vỏ)", "kV"),
            _num("thu_dien_ap_tang_cao.ha_vo", "Hạ – (Cao + vỏ)", "kV"),
            _txt("thu_dien_ap_tang_cao.thoi_gian", "Thời gian thử", "VD: 1 phút"),
        ]},
        {"title": "Kết luận", "fields": [
            {"key": "ket_luan", "label": "Kết luận", "type": "textarea",
             "hint": "Để trống = tool tự sinh “Máy biến áp 3 pha trên đạt yêu cầu…”"},
        ]},
    ],
    # ------------------------------------------------------------------ 45 --
    "45": [
        {"title": "I. Thông tin thiết bị", "fields": [
            # đúng như bản in: “Hiệu: … - Số cực: …” rồi “Loại: … - Kiểu: …”
            _txt("hieu", "Hiệu", "VD: MITSUBISHI"),
            _txt("so_cuc", "Số cực", "VD: 03", type="code"),
            _txt("loai", "Loại", "VD: MCCB", type="select",
                 options=["MCCB", "MCB", "ACB", "ELCB", "RCBO"]),
            _txt("kieu", "Kiểu", "VD: NF-250"),
            _num("dien_ap_dinh_muc", "Điện áp định mức", "V", "VD: 415V"),
            _num("dong_dinh_muc", "Dòng điện định mức", "A", "VD: 250A"),
            _num("dong_ngan_mach_toi_da", "Dòng ngắn mạch tối đa", "kA"),
            _num("tan_so", "Tần số", "Hz", "VD: 50Hz"),
            _num("dien_ap_cach_dien", "Điện áp cách điện định mức", "V"),
            _num("dien_ap_xung", "Điện áp chịu xung định mức", "kV"),
            _txt("kiem_tra_ben_ngoai", "Kiểm tra bên ngoài", "", type="select", options=_NGOAI),
            _txt("so_luong", "Số lượng", "VD: 01", type="code"),
        ]},
        {"title": "II. Bảng kết quả thử nghiệm", "table": {
            "kind": "rows", "key": "rows", "stt": True, "addable": True,
            "columns": [
                {"key": "rcd_close", "label": "R cách điện – Close (MΩ)", "type": "number"},
                {"key": "rcd_open", "label": "R cách điện – Open (MΩ)", "type": "number"},
                {"key": "rtx_a", "label": "R tiếp xúc – Pha A (µΩ)", "type": "number"},
                {"key": "rtx_b", "label": "R tiếp xúc – Pha B (µΩ)", "type": "number"},
                {"key": "rtx_c", "label": "R tiếp xúc – Pha C (µΩ)", "type": "number"},
                {"key": "utest", "label": "Utest (kV/1′)", "type": "number"},
                {"key": "dong_cat", "label": "Đóng Cắt", "type": "number"},
                {"key": "ket_qua", "label": "Kết quả", "type": "select", "options": _KET_QUA},
                {"key": "so_tem", "label": "Số tem", "type": "code"},
            ],
            "new_row": {"rcd_close": ">5000", "rcd_open": ">5000", "rtx_a": "",
                        "rtx_b": "", "rtx_c": "", "utest": "3", "dong_cat": "5",
                        "ket_qua": "Đạt", "so_tem": ""},
            "sync_so_luong": "so_luong",
        }},
        {"title": "Kết luận", "fields": [
            {"key": "ket_luan", "label": "Kết luận", "type": "textarea",
             "hint": "Để trống = tool tự sinh câu kết luận chuẩn"},
        ]},
    ],
    # ---------------------------------------------------------------- 93 --
    # ACB dùng đúng bộ ô và bảng của MCCB (cùng 10 cột, cùng thông số),
    # chỉ khác tên loại máy — nên tái dùng để không lệch chuẩn.
    "93": [
        {"title": "I. Thông tin thiết bị", "fields": [
            _txt("hieu", "Hiệu", "VD: LS"),
            _txt("so_cuc", "Số cực", "VD: 03", type="code"),
            _txt("loai", "Loại", "VD: ACB", type="select",
                 options=["ACB", "MCCB", "MCB", "ELCB", "RCBO"]),
            _txt("kieu", "Kiểu", "VD: AS-25E3-25H"),
            _num("dien_ap_dinh_muc", "Điện áp định mức", "V", "VD: 500V"),
            _num("dong_dinh_muc", "Dòng điện định mức", "A", "VD: 2500A"),
            _num("dong_ngan_mach_toi_da", "Dòng ngắn mạch tối đa", "kA", "VD: 85kA"),
            _num("tan_so", "Tần số", "Hz", "VD: 50/60Hz"),
            _num("dien_ap_cach_dien", "Điện áp cách điện định mức", "V", "VD: 1000V"),
            _num("dien_ap_xung", "Điện áp chịu xung định mức", "kV", "VD: 12kV"),
            _txt("kiem_tra_ben_ngoai", "Kiểm tra bên ngoài", "", type="select", options=_NGOAI),
            _txt("so_luong", "Số lượng", "VD: 01", type="code"),
        ]},
        {"title": "II. Bảng kết quả thử nghiệm", "table": {
            "kind": "rows", "key": "rows", "stt": True, "addable": True,
            "columns": [
                {"key": "rcd_close", "label": "R cách điện – Close (MΩ)", "type": "number"},
                {"key": "rcd_open", "label": "R cách điện – Open (MΩ)", "type": "number"},
                {"key": "rtx_a", "label": "R tiếp xúc – Pha A (µΩ)", "type": "number"},
                {"key": "rtx_b", "label": "R tiếp xúc – Pha B (µΩ)", "type": "number"},
                {"key": "rtx_c", "label": "R tiếp xúc – Pha C (µΩ)", "type": "number"},
                {"key": "utest", "label": "Utest (kV/1′)", "type": "number"},
                {"key": "dong_cat", "label": "Đóng Cắt", "type": "number"},
                {"key": "ket_qua", "label": "Kết quả", "type": "select", "options": _KET_QUA},
                {"key": "so_tem", "label": "Số tem", "type": "code"},
            ],
            "new_row": {"rcd_close": "", "rcd_open": "", "rtx_a": "", "rtx_b": "",
                        "rtx_c": "", "utest": "3", "dong_cat": "5",
                        "ket_qua": "", "so_tem": ""},
            "sync_so_luong": "so_luong",
        }},
        {"title": "Kết luận", "fields": [
            {"key": "ket_luan", "label": "Kết luận", "type": "textarea",
             "hint": "Để trống = tool tự sinh câu kết luận chuẩn"},
        ]},
    ],
    # ---------------------------------------------------------------- 97 --
    "97": [
        {"title": "I. Thông số tuyến cáp", "fields": [
            _txt("so_tem", "Số tem", "VD: 016139", type="code"),
            _txt("doan_cap_tu", "Đoạn cáp đi từ", "VD: Trụ 82/1"),
            _txt("doan_cap_den", "Đến", "VD: Trạm biến áp 1500kVA"),
            _txt("loai_cap", "Loại cáp", "VD: Cáp ngầm trung thế"),
            _txt("tiet_dien", "Tiết diện", "VD: 3 x 50mm2"),
            _num("dien_ap_dinh_muc", "Điện áp định mức", "kV", "VD: 12,7/22(24)kV"),
            _num("tan_so", "Tần số", "Hz", "VD: 50Hz"),
            _num("nhiet_do", "Nhiệt độ", "°C", "VD: 34"),
            _txt("kiem_tra_ben_ngoai", "Kiểm tra bên ngoài", "", type="select", options=_NGOAI),
        ]},
        {"title": "II. Điện trở cách điện theo pha", "table": {
            "kind": "fixed", "key": "r_cach_dien_Mohm", "columns": [
                {"key": "tieu_chuan", "label": "Tiêu chuẩn (MΩ)", "type": "number"},
                {"key": "so_lieu_do", "label": "Số liệu đo (MΩ)", "type": "number"},
            ],
            "rows": [
                {"key": "pha1", "label": "Pha 1 – (2+3+vỏ)"},
                {"key": "pha2", "label": "Pha 2 – (1+3+vỏ)"},
                {"key": "pha3", "label": "Pha 3 – (1+2+vỏ)"},
            ],
        }},
        {"title": "III. Điện áp một chiều tăng cao", "table": {
            "kind": "fixed", "key": "thu_dien_ap_mot_chieu", "columns": [
                {"key": "thoi_gian", "label": "Thời gian (phút)", "type": "number"},
                {"key": "dien_ap", "label": "Điện áp thử (kV)", "type": "number"},
                {"key": "dong_ro", "label": "Dòng rò (µA)", "type": "number"},
            ],
            "rows": [
                {"key": "pha1", "label": "Pha 1 – (2+3+vỏ)"},
                {"key": "pha2", "label": "Pha 2 – (1+3+vỏ)"},
                {"key": "pha3", "label": "Pha 3 – (1+2+vỏ)"},
            ],
        }},
        {"title": "Kết luận", "fields": [
            {"key": "ket_luan", "label": "Kết luận", "type": "textarea",
             "hint": "Để trống = tool tự sinh câu kết luận chuẩn"},
        ]},
    ],
    # ------------------------------------------------------------------ 46 --
    "46": [
        {"title": "I. Thông tin thiết bị", "fields": [
            _txt("vat_lieu", "Vật liệu cách điện", "VD: Polymer", type="select",
                 options=["Polymer", "Sứ"]),
            _num("mcov", "MCOV", "kV", "VD: 15,3kV"),
            _num("dien_ap_dinh_muc", "Điện áp định mức", "kV", "VD: 18kV"),
            _num("tan_so", "Tần số", "Hz", "VD: 50Hz"),
            _num("dong_xa_toi_da", "Dòng điện xả tối đa", "kA", "VD: 10 kA"),
            _txt("kiem_tra_ben_ngoai", "Kiểm tra bên ngoài", "", type="select", options=_NGOAI),
            _txt("so_luong", "Số lượng", "VD: 01", type="code"),
        ]},
        {"title": "II. Bảng kết quả kiểm định", "table": {
            "kind": "rows", "key": "rows", "stt": False, "addable": True,
            "columns": [
                {"key": "doi_tuong_do", "label": "Đối tượng đo", "type": "text",
                 "hint": "VD: LA 01"},
                {"key": "r_cach_dien", "label": "Điện trở cách điện (MΩ)", "type": "number"},
                {"key": "dong_ro", "label": "Dòng điện rò ở Uđm (µA)", "type": "number"},
                {"key": "u_ac", "label": "Điện áp AC tăng cao (kV)", "type": "number"},
            ],
            "new_row": {"doi_tuong_do": "", "r_cach_dien": ">10000",
                        "dong_ro": "", "u_ac": ""},
            "sync_so_luong": "so_luong",
        }},
        {"title": "Kết luận", "fields": [
            {"key": "ket_luan", "label": "Kết luận", "type": "textarea",
             "hint": "Để trống = tool tự sinh câu kết luận chuẩn"},
        ]},
    ],
    # ------------------------------------------------------------------ 47 --
    "47": [
        {"title": "I. Thông tin thiết bị", "fields": [
            _txt("vat_lieu", "Vật liệu cách điện", "VD: Sứ", type="select",
                 options=["Sứ", "Polymer", "Thủy tinh"]),
            _num("dong_dinh_muc", "Dòng điện định mức", "A", "VD: 100A"),
            _num("dien_ap_dinh_muc", "Điện áp định mức", "kV", "VD: 27kV"),
            _num("kha_nang_cat_ngan_mach", "Khả năng cắt ngắn mạch", "kA", "VD: 12kA"),
            _txt("kiem_tra_ben_ngoai", "Kiểm tra bên ngoài", "", type="select", options=_NGOAI),
            _txt("so_luong", "Số lượng", "VD: 01", type="code"),
        ]},
        {"title": "II. Bảng kết quả kiểm định", "table": {
            "kind": "rows", "key": "rows", "stt": False, "addable": True,
            "columns": [
                {"key": "thiet_bi", "label": "Thiết bị", "type": "text", "hint": "VD: FCO 01"},
                {"key": "rcd_truoc", "label": "R cách điện – trước thử cao áp (MΩ)", "type": "number"},
                {"key": "rcd_sau", "label": "R cách điện – sau thử cao áp (MΩ)", "type": "number"},
                {"key": "ac_kho", "label": "Điện áp AC – điều kiện khô (kV)", "type": "number"},
                {"key": "ac_uot", "label": "Điện áp AC – điều kiện ướt (kV)", "type": "number"},
                {"key": "dong_cat", "label": "Đóng Cắt", "type": "number"},
                {"key": "ket_qua", "label": "Kết quả", "type": "select", "options": _KET_QUA},
            ],
            "new_row": {"thiet_bi": "", "rcd_truoc": ">10000", "rcd_sau": ">10000",
                        "ac_kho": "60", "ac_uot": "50", "dong_cat": "5", "ket_qua": "Đạt"},
            "sync_so_luong": "so_luong",
        }},
        {"title": "Kết luận", "fields": [
            {"key": "ket_luan", "label": "Kết luận", "type": "textarea",
             "hint": "Để trống = tool tự sinh câu kết luận chuẩn"},
        ]},
    ],
    # ------------------------------------------------------------------ 48 --
    "48": [
        {"title": "I. Bảng kết quả đo điện trở nối đất", "table": {
            "kind": "rows", "key": "rows", "stt": True, "addable": True,
            "columns": [
                {"key": "chi_danh", "label": "Chỉ danh", "type": "text",
                 "hint": "VD: Điện trở nối đất trạm biến áp"},
                {"key": "ket_noi_trung_tinh", "label": "Tình trạng kết nối với trung tính hệ thống",
                 "type": "select", "options": ["Có", "Không"]},
                {"key": "loai_tiep_dat", "label": "Loại tiếp đất", "type": "select",
                 "options": ["Làm việc", "Chống sét", "An toàn", "Lặp lại"]},
                {"key": "gia_tri_do", "label": "Giá trị đo (Ω)", "type": "number"},
            ],
            "new_row": {"chi_danh": "", "ket_noi_trung_tinh": "Có",
                        "loai_tiep_dat": "Làm việc", "gia_tri_do": ""},
            "sync_so_luong": None,
        }},
        {"title": "Thiết bị thử nghiệm", "fields": [
            _txt("thiet_bi_do", "Thiết bị đo", "VD: KEW 4105DL"),
        ]},
    ],
}

# Mẫu 48: các ô phẳng cũ được giữ để tương thích ngược (JSON cũ chỉ có 1 dòng).
FLAT_48 = ["chi_danh", "ket_noi_trung_tinh", "loai_tiep_dat", "gia_tri_do_Ohm"]


def web_groups(form: str) -> list[dict]:
    """Khối để dựng form, **theo đúng thứ tự in**.

    1. ``header``  – SỐ + NGÀY (khối tiêu đề của mọi mẫu);
    2. ``before_common`` – khối đứng trước phần thông tin công trình
       (mẫu 44: “Lý lịch thiết bị” nằm trên Tên công trình);
    3. ``project`` – tên công trình → địa chỉ → chỉ danh → đơn vị yêu cầu →
       lý do → nơi → ngày kiểm định;
    4. phần còn lại của mẫu (quy cách, bảng số liệu, kết luận…), cuối cùng là
       khối chữ ký.

    Ô riêng của biên bản được gắn tiền tố ``__block`` + mã mẫu để web ghi
    đúng vào ``DATA["bien_ban_45_mccb"]`` chứ không phải cấp ngoài cùng.
    """
    head = [f for f in COMMON_GROUP["fields"] if f.get("part") == "header"]
    sign = [f for f in COMMON_GROUP["fields"] if f.get("part") == "signature"]
    project = []
    for f in COMMON_GROUP["fields"]:
        if f.get("part") in ("header", "signature"):
            continue
        if form not in (f.get("only") or [form]):
            continue
        f = dict(f)
        if f["path"][0] == "__block_field__":      # ô nằm trong biên bản, không phải ô chung
            f["path"] = ["__block", form] + list(f["path"][1:])
        project.append(f)
    groups: list[dict] = [
        {"title": "Khung biên bản (SỐ / NGÀY)", "fields": head},
        {"title": "Thông tin công trình", "fields": project},
    ]
    for g in FORM_GROUPS[form]:
        g = dict(g)
        if "fields" in g:
            g["fields"] = [
                dict(f, path=["__block", form] + list(f.get("path") or f["key"].split(".")))
                for f in g["fields"]
            ]
        if g.get("position") == "before_common":
            groups.insert(1, g)
        else:
            groups.append(g)
    groups.append({"title": "Người ký (in ở hàng chữ ký cuối biên bản)", "fields": sign})
    return groups


def print_order(form: str) -> list[str]:
    """Thứ tự nhãn **sẽ in ra** của một mẫu — dùng để đối chiếu với file Word."""
    out: list[str] = []
    for g in web_groups(form):
        if "table" in g:
            out.append("[bảng] " + g["title"])
            continue
        out.extend(f["label"] for f in g.get("fields", []))
    return out


def get_groups(form: str) -> list[dict]:
    return FORM_GROUPS[form]


def fields_of(form: str):
    """Sinh mọi ô đơn của một mẫu (đã bỏ bảng), kèm ``path`` đầy đủ."""
    for g in FORM_GROUPS[form]:
        for f in g.get("fields", []):
            f = dict(f)
            f.setdefault("path", f["key"].split("."))
            yield f


def tables_of(form: str):
    for g in FORM_GROUPS[form]:
        if "table" in g:
            yield g["title"], g["table"]


def web_schema() -> dict:
    """Cấu trúc gửi xuống JS để dựng form chỉnh sửa."""
    return {
        "common": COMMON_GROUP,
        "forms": {
            form: {
                "title": TITLES[form],
                "file": TEMPLATES[form],
                "groups": web_groups(form),
            }
            for form in sorted(FORM_GROUPS)
        },
    }


# --------------------------------------------------------------------------- #
# Gộp nhiều lần đọc ảnh thành một bộ dữ liệu
# --------------------------------------------------------------------------- #
#: Những khoá chứa dãy số cố định (không phải bảng tự do)
_SERIES_KEYS = ("ti_so_bien_ap", "r_cuon_day_1_chieu_ohm", "thu_dien_ap_tang_cao",
                "ngan_mach", "khong_tai", "u_ac_tang_cao_kV", "r_cach_dien_Mohm",
                "r_tiep_xuc_uohm")


def _is_blank(v) -> bool:
    return v in (None, "", [], {}) or (isinstance(v, str) and not v.strip())


def _table_of_block(block: dict) -> tuple[str, list] | None:
    """Tìm bảng trong một khối dữ liệu: ``rows`` hoặc ``rows.rows``."""
    for key in ("rows", "table"):
        val = block.get(key)
        if isinstance(val, list):
            return key, val
        if isinstance(val, dict) and isinstance(val.get("rows"), list):
            return key, val["rows"]
    return None


def _set_table(block: dict, key: str, rows: list) -> None:
    if isinstance(block.get(key), dict):
        block[key]["rows"] = rows
    else:
        block[key] = rows


def _renumber(rows: list) -> list:
    """Đánh lại STT 01, 02… cho bảng sau khi gộp."""
    n = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if "stt" in row or len(rows) > 1:
            n += 1
            if "stt" in row:
                row["stt"] = f"{n:02d}"
    return rows


def merge_results(results: list[dict]) -> tuple[dict, list[str]]:
    """Gộp kết quả nhận dạng của nhiều nhóm ảnh thành **một** bộ dữ liệu.

    Nghiệp vụ: mỗi mẫu (44–48) in ra **một** biên bản, và một biên bản có thể
    liệt kê nhiều thiết bị trong bảng. Vì vậy khi hai nhóm ảnh cùng là mẫu 45:

    * thông tin chung ``thong_tin_chung``: nhóm sau chỉ bổ sung ô còn trống,
      không ghi đè ô nhóm trước đã đọc được;
    * các ô đơn (số biên bản, ngày…): giữ giá trị đầu tiên đọc được;
    * **bảng**: nối các dòng lại và đánh lại STT → nhiều thiết bị vẫn in đủ
      trên một biên bản;
    * dãy số cố định (``ti_so_bien_ap``…): giữ dãy đầu tiên, ghi chú phần bỏ.

    Trả về ``(data, notes)`` – ``notes`` là các ghi chú tiếng Việt cho người dùng
    biết đã gộp gì.
    """
    notes: list[str] = []
    out: dict = {}
    common: dict = {}
    crew: dict = {}

    for res in results:
        if not isinstance(res, dict):
            continue
        tt = res.get("thong_tin_chung") or {}
        if isinstance(tt, dict):
            for k, v in tt.items():
                if k == "can_bo_ky_ten" and isinstance(v, dict):
                    for ck, cv in v.items():
                        if _is_blank(crew.get(ck)) and not _is_blank(cv):
                            crew[ck] = cv
                elif _is_blank(common.get(k)) and not _is_blank(v):
                    common[k] = v
        for key, block in res.items():
            if key in ("thong_tin_chung", "_ai") or not isinstance(block, dict):
                continue
            if key not in out:
                out[key] = json.loads(json.dumps(block, ensure_ascii=False))
                continue
            # ---- đã có khối cùng mẫu: gộp ----
            cur = out[key]
            extra_rows: list = []
            for field, value in block.items():
                if _is_blank(value):
                    continue
                if field in ("rows", "table"):
                    continue
                if field in _SERIES_KEYS and not _is_blank(cur.get(field)):
                    if value != cur.get(field):
                        notes.append(
                            f"{key}: giữ dãy số của nhóm đầu, bỏ dãy trùng ở nhóm sau")
                    continue
                if _is_blank(cur.get(field)):
                    cur[field] = value
            tbl = _table_of_block(block)
            if tbl:
                extra_rows = [r for r in tbl[1] if isinstance(r, dict)]
            if extra_rows:
                cur_tbl = _table_of_block(cur)
                if cur_tbl:
                    _set_table(cur, cur_tbl[0], _renumber(list(cur_tbl[1]) + extra_rows))
                else:
                    _set_table(cur, tbl[0], _renumber(extra_rows))
                notes.append(
                    f"{key}: gộp thêm {len(extra_rows)} dòng thiết bị "
                    f"(tổng {len(_table_of_block(cur)[1])} dòng)")

    if crew:
        common["can_bo_ky_ten"] = crew
    data: dict = {}
    if common:
        data["thong_tin_chung"] = common
    data.update(out)
    return data, notes
