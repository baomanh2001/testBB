from typing import Any, Dict

SAMPLE_IMAGES = {
    "meter": "1793774540596_4641126229309712981_4641126229309712981_48781e09ae3965051ec46cd630b7a734.jpg",
    "mba_p1": "1793774541459_4641126229309712981_4641126229309712981_07ee685b68694cb264f1aa62b4d5f9ac.jpg",
    "mba_p2": "1793774542546_4641126229309712981_4641126229309712981_f73eddb68b273394643ad357c1605145.jpg",
    "mccb": "1793774543325_4641126229309712981_4641126229309712981_b32a099a41fd6bc7000ea71e029ff05a.jpg",
    "dtnd": "1793774544075_4641126229309712981_4641126229309712981_9a483da05aba3c5a4307d31c53884cb8.jpg",
    "fco": "1793774544827_4641126229309712981_4641126229309712981_92be31a5ef12a129fa4073b70fa931de.jpg",
    "la": "1793774545590_4641126229309712981_4641126229309712981_4e0466ee364b8d15e965d760b6f47e2f.jpg",
}


def get_sample_batch() -> Dict[str, Any]:
    common_project = {
        "ten_cong_trinh": "Trạm biến áp 50kVA – DOANH NGHIỆP TƯ NHÂN E-GREEN",
        "dia_chi": "Khu phố Gia Huỳnh, Phường Trảng Bàng, Tỉnh Tây Ninh, Việt Nam",
        "don_vi_yeu_cau": "DOANH NGHIỆP TƯ NHÂN E-GREEN",
        "ly_do": "Sau sự cố",
        "noi_kiem_dinh": "Tại hiện trường",
        "ngay_kiem_dinh": "01/11/2026",
        "ngay_phat_hanh": "04/11/2026",
        "stt_bat_dau": 44,
        "ma_thang_nam": "1126",
    }

    signatory = {
        "nguoi_thu": "Nguyễn Trung Nghĩa",
        "kiem_tra": "Nguyễn Minh Quân",
        "pho_giam_doc": "Nguyễn Nhật Tân",
        "include_signature": True,
    }

    context_photos = [
        {
            "label": "Ảnh công tơ / Nhãn trạm (E-GREEN - Trụ 34/22/3/1)",
            "url": f"/api/sample-images/{SAMPLE_IMAGES['meter']}",
            "filename": SAMPLE_IMAGES["meter"],
            "note": "Trích xuất pháp nhân chuẩn: DOANH NGHIỆP TƯ NHÂN E-GREEN (Trụ 34/22/3/1, TI: 250/5, CE-14)",
        }
    ]

    reports = [
        {
            "id": "sample-44",
            "stt_file": 44,
            "report_type": "mba_1p",
            "filename": "44 BB MBA 1P 50KVA.docx",
            "images": [
                {"label": "Trang 1/2 (MBA 1P)", "url": f"/api/sample-images/{SAMPLE_IMAGES['mba_p1']}"},
                {"label": "Trang 2/2 (MBA 1P)", "url": f"/api/sample-images/{SAMPLE_IMAGES['mba_p2']}"},
                {"label": "Ảnh Công tơ trạm", "url": f"/api/sample-images/{SAMPLE_IMAGES['meter']}"},
            ],
            "ai_notes": [
                "Đã tự động gộp Trang 1/2 và Trang 2/2 thành 1 biên bản Máy biến áp 1 pha hoàn chỉnh.",
                "Chuẩn hóa 'VN' → 'Việt Nam', 'TBA 50kVA - DNTN E-Green' → 'Trạm biến áp 50kVA – DOANH NGHIỆP TƯ NHÂN E-GREEN'.",
                "Hiệu chỉnh tổ đấu dây ghi tay 'Dyn 11' sang đúng chuẩn máy 1 pha 'I/I0'.",
                "Lưu ý kiểm tra: Ô Tỉ số biến áp Hạ 1 - Nấc 1 trên ảnh viết '57,95' (file .doc cũ ghi 57,98).",
            ],
            "common": {
                "so_bien_ban": "50441126/BB-TC",
                "ngay_phat_hanh": "04/11/2026",
                "loai_tieu_de": "BIÊN BẢN KIỂM ĐỊNH",
                "ten_cong_trinh": common_project["ten_cong_trinh"],
                "dia_chi": common_project["dia_chi"],
                "chi_danh": "MBA 1P 50kVA",
                "don_vi_yeu_cau": common_project["don_vi_yeu_cau"],
                "ly_do": common_project["ly_do"],
                "noi_kiem_dinh": "Tại hiện trường",
                "ngay_kiem_dinh": "01/11/2026",
            },
            "signatory": signatory,
            "data": {
                "so_tem": "017246",
                "hieu_may": "EMC",
                "so_may": "04080468",
                "nuoc_san_xuat": "Việt Nam",
                "nam_san_xuat": "2004",
                "cong_suat_dinh_muc": "50kVA",
                "so_pha": "1",
                "tan_so": "50Hz",
                "dien_ap_dinh_muc": "12,7/0,23 (kV)",
                "to_dau_day": "I/I0",
                "kiem_tra_ben_ngoai": "Bình thường",
                "cach_dien_rows": [
                    {"doi_tuong_do": "(Cao+Vỏ) –Hạ 1", "r60": "2760", "r15": "2106", "kht": "1,31"},
                    {"doi_tuong_do": "(Cao+vỏ) –Hạ 2", "r60": "2550", "r15": "1902", "kht": "1,34"},
                    {"doi_tuong_do": "Hạ 1 – Hạ 2", "r60": "1790", "r15": "1376", "kht": "1,30"},
                ],
                "dien_tro_cao_ap": ["16,42", "15,98", "15,57", "15,12", "14,68"],
                "dien_tro_ha_1": "8,832",
                "dien_tro_ha_2": "8,824",
                "ti_so_ha_1": ["57,95", "56,59", "55,21", "53,83", "52,46"],
                "ti_so_ha_2": ["57,95", "56,57", "55,25", "53,87", "52,44"],
                "khong_tai_u0": "230",
                "khong_tai_i0": "1,58",
                "khong_tai_i0_pct": "0,73",
                "khong_tai_p0": "97,6",
                "ngan_mach_un": "304,7",
                "ngan_mach_un_pct": "2,4",
                "ngan_mach_in": "3,94",
                "ngan_mach_pn75": "563,2",
                "dien_ap_tang_cao_rows": [
                    {"doi_tuong_thu": "Cuộn dây cao áp", "u_thu": "50", "thoi_gian": "1 phút"},
                    {"doi_tuong_thu": "Cuộn dây hạ áp", "u_thu": "3", "thoi_gian": "1 phút"},
                ],
                "thiet_bi_kiem_dinh": "Kyoritsu 3125A, C.A 6255, DTR 8510, HVTS-70/50, Multimeter, Variac.",
                "ket_luan": "Máy biến áp 1 pha trên đạt yêu cầu đóng điện vận hành.",
            },
        },
        {
            "id": "sample-45",
            "stt_file": 45,
            "report_type": "mccb",
            "filename": "45 MCCB 250A.docx",
            "images": [
                {"label": "Biên bản MCCB 250A", "url": f"/api/sample-images/{SAMPLE_IMAGES['mccb']}"},
            ],
            "ai_notes": [
                "Chuẩn hóa Hiệu 'Mitsubishi' → 'MITSUBISHI'; các ô Uđm, Icu để trống → '-'.",
                "Lưu ý kiểm tra: Ô Số tem trên ảnh viết tay nhìn giống '017245' (liền kề tem MBA 017246), bản mẫu cũ ghi '017215'.",
            ],
            "common": {
                "so_bien_ban": "50451126/BB-TC",
                "ngay_phat_hanh": "04/11/2026",
                "loai_tieu_de": "BIÊN BẢN KIỂM ĐỊNH",
                "ten_cong_trinh": common_project["ten_cong_trinh"],
                "dia_chi": common_project["dia_chi"],
                "chi_danh": "MCCB 250A",
                "don_vi_yeu_cau": common_project["don_vi_yeu_cau"],
                "ly_do": common_project["ly_do"],
                "noi_kiem_dinh": "Tại hiện trường",
                "ngay_kiem_dinh": "01/11/2026",
            },
            "signatory": signatory,
            "data": {
                "hieu": "MITSUBISHI",
                "so_cuc": "03",
                "loai": "MCCB",
                "kieu": "NF-250",
                "dien_ap_dinh_muc": "-",
                "dong_dien_dinh_muc": "250A",
                "dong_ngan_mach": "-",
                "tan_so": "50Hz",
                "dien_ap_cach_dien": "-",
                "dien_ap_xung": "-",
                "kiem_tra_ben_ngoai": "Bình thường",
                "so_luong": "01",
                "rows": [
                    {
                        "stt": "1",
                        "rcd_close": ">5000",
                        "rcd_open": ">5000",
                        "rtx_a": "273",
                        "rtx_b": "275",
                        "rtx_c": "279",
                        "utest": "3",
                        "dong_cat": "5",
                        "ket_qua": "Đạt",
                        "so_tem": "017245",
                    }
                ],
                "thiet_bi_kiem_dinh": "Kyoritsu 3165; Kyoritsu 3125A; CA 6255; CA 6292; HVT-70/50",
                "tieu_chuan_kiem_dinh": "QCVN QTĐ-5: 2009/BCT; QT/TNMCĐ",
                "ket_luan": "01 máy cắt hạ thế (MCCB) trên đạt yêu cầu đóng điện vận hành.",
            },
        },
        {
            "id": "sample-46",
            "stt_file": 46,
            "report_type": "la",
            "filename": "46 BB LA.docx",
            "images": [
                {"label": "Biên bản LA", "url": f"/api/sample-images/{SAMPLE_IMAGES['la']}"},
            ],
            "ai_notes": [
                "Tự động đổi đơn vị MCOV ghi tay '15300V' → '15,3kV' theo chuẩn biểu mẫu.",
                "Đã loại bỏ các dòng trống gạch chéo LA 02..06.",
            ],
            "common": {
                "so_bien_ban": "50461126/BB-TC",
                "ngay_phat_hanh": "04/11/2026",
                "loai_tieu_de": "BIÊN BẢN KIỂM ĐỊNH",
                "ten_cong_trinh": common_project["ten_cong_trinh"],
                "dia_chi": common_project["dia_chi"],
                "chi_danh": "LA 18kV-10kA",
                "don_vi_yeu_cau": common_project["don_vi_yeu_cau"],
                "ly_do": common_project["ly_do"],
                "noi_kiem_dinh": "Tại hiện trường",
                "ngay_kiem_dinh": "01/11/2026",
            },
            "signatory": signatory,
            "data": {
                "vat_lieu_cach_dien": "Polymer",
                "mcov": "15,3kV",
                "dien_ap_dinh_muc": "18kV",
                "tan_so": "50Hz",
                "dong_dien_xa": "10 kA",
                "kiem_tra_ben_ngoai": "Bình thường",
                "so_luong": "01",
                "rows": [
                    {
                        "doi_tuong_do": "LA 01",
                        "dien_tro_cach_dien": ">10000",
                        "dong_dien_ro": "17",
                        "dien_ap_ac": "35",
                    }
                ],
                "tieu_chuan_kiem_dinh": "QCVN QTĐ-5,6,7: 2009/BCT",
                "thiet_bi_kiem_dinh": "Kyoritsu 3125A ; HVT-70/50",
                "ket_luan": "Một (01) chống sét van trên đạt yêu cầu đóng điện vận hành",
            },
        },
        {
            "id": "sample-47",
            "stt_file": 47,
            "report_type": "fco",
            "filename": "47 BB FCO.docx",
            "images": [
                {"label": "Biên bản FCO", "url": f"/api/sample-images/{SAMPLE_IMAGES['fco']}"},
            ],
            "ai_notes": [
                "Nhận diện chỗ gạch sửa tay Vật liệu cách điện 'Polymer' → lấy giá trị đã sửa là 'Sứ'.",
                "Nhận diện Điện áp định mức sửa tay → '27kV'.",
            ],
            "common": {
                "so_bien_ban": "50471126/BB-TC",
                "ngay_phat_hanh": "04/11/2026",
                "loai_tieu_de": "BIÊN BẢN KIỂM ĐỊNH",
                "ten_cong_trinh": common_project["ten_cong_trinh"],
                "dia_chi": common_project["dia_chi"],
                "chi_danh": "FCO – 100A",
                "don_vi_yeu_cau": common_project["don_vi_yeu_cau"],
                "ly_do": common_project["ly_do"],
                "noi_kiem_dinh": "Tại hiện trường",
                "ngay_kiem_dinh": "01/11/2026",
            },
            "signatory": signatory,
            "data": {
                "vat_lieu_cach_dien": "Sứ",
                "dong_dien_dinh_muc": "100A",
                "dien_ap_dinh_muc": "27kV",
                "kha_nang_cat_ngan_mach": "12kA",
                "kiem_tra_ben_ngoai": "Bình thường",
                "so_luong": "01",
                "rows": [
                    {
                        "thiet_bi": "FCO 01",
                        "rcd_truoc": ">10000",
                        "rcd_sau": ">10000",
                        "ac_kho": "60",
                        "ac_uot": "50",
                        "dong_cat": "5",
                        "ket_qua": "Đạt",
                    }
                ],
                "tieu_chuan_kiem_dinh": "QCVN QTĐ-5,6,7: 2009/BCT",
                "thiet_bi_kiem_dinh": "Kyoritsu 3125A; I/IOM 100",
                "ket_luan": "Một (01) FCO trên đạt yêu cầu đóng điện vận hành",
            },
        },
        {
            "id": "sample-48",
            "stt_file": 48,
            "report_type": "dtnd",
            "filename": "48 BB điện trở nối đất.docx",
            "images": [
                {"label": "Biên bản Điện trở nối đất", "url": f"/api/sample-images/{SAMPLE_IMAGES['dtnd']}"},
            ],
            "ai_notes": [
                "Mở rộng viết tắt 'Điện trở nối đất TBA' → 'Điện trở nối đất trạm biến áp'.",
                "Sử dụng tiêu đề 'BIÊN BẢN THỬ NGHIỆM' đúng mẫu Điện trở nối đất.",
            ],
            "common": {
                "so_bien_ban": "50481126/BB-TC",
                "ngay_phat_hanh": "04/11/2026",
                "loai_tieu_de": "BIÊN BẢN THỬ NGHIỆM",
                "ten_cong_trinh": common_project["ten_cong_trinh"],
                "dia_chi": common_project["dia_chi"],
                "chi_danh": "Điện trở nối đất",
                "don_vi_yeu_cau": common_project["don_vi_yeu_cau"],
                "ly_do": common_project["ly_do"],
                "noi_kiem_dinh": "Hiện trường",
                "ngay_kiem_dinh": "01/11/2026",
            },
            "signatory": signatory,
            "data": {
                "rows": [
                    {
                        "stt": "1",
                        "chi_danh": "Điện trở nối đất trạm biến áp",
                        "ket_noi_trung_tinh": "Có",
                        "loai_tiep_dat": "Làm việc",
                        "gia_tri_do": "3,52",
                    }
                ],
                "thiet_bi_thu_nghiem": "KEW 4105DL",
                "ghi_chu_1": "Chỉ danh, vị trí cọc nối đất do đơn vị yêu cầu thử nghiệm cung cấp",
                "ghi_chu_2": "Các kết quả đo chỉ có giá trị đối với điểm đo",
            },
        },
    ]

    return {
        "common_project": common_project,
        "signatory": signatory,
        "context_photos": context_photos,
        "reports": reports,
    }
