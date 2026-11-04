from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

ReportType = Literal[
    "mba_1p",
    "mba_3p",
    "mccb",
    "acb",
    "la",
    "fco",
    "lbfco",
    "dtnd",
    "cap_ngam",
    "tu_bu",
]


class SignatoryInfo(BaseModel):
    nguoi_thu: str = "Nguyễn Trung Nghĩa"
    kiem_tra: str = "Nguyễn Minh Quân"
    pho_giam_doc: str = "Nguyễn Nhật Tân"
    include_signature: bool = True
    custom_signature_data_url: Optional[str] = None


class CompanyInfo(BaseModel):
    ten_cong_ty: str = "CÔNG TY CP THÍ NGHIỆM ĐIỆN TOÀN CẦU"
    footer_text: str = (
        "ĐC: 213/21 TTH07, Phường Tân Thới Hiệp, TP.HCM                  "
        "Điện thoại: 0908 206 854                  "
        "Website: http://thinghiemdientoancau.com"
    )


class CommonHeader(BaseModel):
    so_bien_ban: str = ""
    ngay_phat_hanh: str = ""
    loai_tieu_de: str = "BIÊN BẢN KIỂM ĐỊNH"
    ten_cong_trinh: str = ""
    dia_chi: str = ""
    chi_danh: str = ""
    don_vi_yeu_cau: str = ""
    ly_do: str = ""
    noi_kiem_dinh: str = ""
    ngay_kiem_dinh: str = ""


# --- 1. Máy biến áp 1 pha (MBA 1P) ---
class MbaInsulationRow(BaseModel):
    doi_tuong_do: str = "(Cao+Vỏ) –Hạ 1"
    r60: str = "2760"
    r15: str = "2106"
    kht: str = "1,31"


class MbaAcWithstandRow(BaseModel):
    doi_tuong_thu: str = "Cuộn dây cao áp"
    u_thu: str = "50"
    thoi_gian: str = "1 phút"


class Mba1PData(BaseModel):
    so_tem: str = "017246"
    hieu_may: str = "EMC"
    so_may: str = "04080468"
    nuoc_san_xuat: str = "Việt Nam"
    nam_san_xuat: str = "2004"
    cong_suat_dinh_muc: str = "50kVA"
    so_pha: str = "1"
    tan_so: str = "50Hz"
    dien_ap_dinh_muc: str = "12,7/0,23 (kV)"
    to_dau_day: str = "I/I0"
    kiem_tra_ben_ngoai: str = "Bình thường"
    cach_dien_rows: List[MbaInsulationRow] = Field(
        default_factory=lambda: [
            MbaInsulationRow(doi_tuong_do="(Cao+Vỏ) –Hạ 1", r60="2760", r15="2106", kht="1,31"),
            MbaInsulationRow(doi_tuong_do="(Cao+vỏ) –Hạ 2", r60="2550", r15="1902", kht="1,34"),
            MbaInsulationRow(doi_tuong_do="Hạ 1 – Hạ 2", r60="1790", r15="1376", kht="1,30"),
        ]
    )
    dien_tro_cao_ap: List[str] = Field(default_factory=lambda: ["16,42", "15,98", "15,57", "15,12", "14,68"])
    dien_tro_ha_1: str = "8,832"
    dien_tro_ha_2: str = "8,824"
    ti_so_ha_1: List[str] = Field(default_factory=lambda: ["57,95", "56,59", "55,21", "53,83", "52,46"])
    ti_so_ha_2: List[str] = Field(default_factory=lambda: ["57,95", "56,57", "55,25", "53,87", "52,44"])
    khong_tai_u0: str = "230"
    khong_tai_i0: str = "1,58"
    khong_tai_i0_pct: str = "0,73"
    khong_tai_p0: str = "97,6"
    ngan_mach_un: str = "304,7"
    ngan_mach_un_pct: str = "2,4"
    ngan_mach_in: str = "3,94"
    ngan_mach_pn75: str = "563,2"
    dien_ap_tang_cao_rows: List[MbaAcWithstandRow] = Field(
        default_factory=lambda: [
            MbaAcWithstandRow(doi_tuong_thu="Cuộn dây cao áp", u_thu="50", thoi_gian="1 phút"),
            MbaAcWithstandRow(doi_tuong_thu="Cuộn dây hạ áp", u_thu="3", thoi_gian="1 phút"),
        ]
    )
    thiet_bi_kiem_dinh: str = "Kyoritsu 3125A, C.A 6255, DTR 8510, HVTS-70/50, Multimeter, Variac."
    ket_luan: str = "Máy biến áp 1 pha trên đạt yêu cầu đóng điện vận hành."


# --- 2. Máy biến áp 3 pha (MBA 3P) ---
class Mba3PDcTapRow(BaseModel):
    nac: str = "1"
    ab: str = "3,413"
    bc: str = "3,418"
    ca: str = "3,421"


class Mba3PRatioRow(BaseModel):
    nac: str = "1"
    k1: str = "57,759"
    k2: str = "57,763"
    k3: str = "57,764"


class Mba3PData(BaseModel):
    so_tem: str = "016140"
    hieu_may: str = "THIBIDI"
    so_may: str = "103150017"
    nuoc_san_xuat: str = "Việt Nam"
    nam_san_xuat: str = "2010"
    cong_suat_dinh_muc: str = "1500kVA"
    so_pha: str = "03"
    tan_so: str = "50 Hz"
    dien_ap_dinh_muc: str = "22/0.4kV"
    to_dau_day: str = "Dyn11"
    kiem_tra_ben_ngoai: str = "Bình thường"
    nhiet_do: str = "34⁰C"
    cach_dien_rows: List[MbaInsulationRow] = Field(
        default_factory=lambda: [
            MbaInsulationRow(doi_tuong_do="Cao – Vỏ", r60="15300", r15="11300", kht="1,35"),
            MbaInsulationRow(doi_tuong_do="Cao – Hạ", r60="13700", r15="10200", kht="1,34"),
            MbaInsulationRow(doi_tuong_do="Hạ – Vỏ", r60="8200", r15="6200", kht="1,32"),
        ]
    )
    dc_cao_ap_rows: List[Mba3PDcTapRow] = Field(
        default_factory=lambda: [
            Mba3PDcTapRow(nac="1", ab="3,413", bc="3,418", ca="3,421"),
            Mba3PDcTapRow(nac="2", ab="3,332", bc="3,336", ca="3,339"),
            Mba3PDcTapRow(nac="3", ab="3,251", bc="3,255", ca="3,258"),
            Mba3PDcTapRow(nac="4", ab="3,169", bc="3,174", ca="3,177"),
            Mba3PDcTapRow(nac="5", ab="3,088", bc="3,092", ca="3,095"),
        ]
    )
    dc_ha_an: str = "an: 0,885"
    dc_ha_bn: str = "bn: 0,887"
    dc_ha_cn: str = "cn: 0,889"
    ti_so_rows: List[Mba3PRatioRow] = Field(
        default_factory=lambda: [
            Mba3PRatioRow(nac="1", k1="57,759", k2="57,763", k3="57,764"),
            Mba3PRatioRow(nac="2", k1="56,384", k2="56,387", k3="56,388"),
            Mba3PRatioRow(nac="3", k1="55,019", k2="55,012", k3="55,013"),
            Mba3PRatioRow(nac="4", k1="53,633", k2="53,637", k3="53,638"),
            Mba3PRatioRow(nac="5", k1="52,258", k2="52,261", k3="52,262"),
        ]
    )
    khong_tai_u0: str = "400"
    khong_tai_i0: str = "5,19"
    khong_tai_i0_pct: str = "0,24"
    khong_tai_p0: str = "1210,3"
    ngan_mach_un: str = "1280,4"
    ngan_mach_un_pct: str = "5,82"
    ngan_mach_in: str = "39,36"
    ngan_mach_pn75: str = "12423,3"
    dien_ap_tang_cao_rows: List[MbaAcWithstandRow] = Field(
        default_factory=lambda: [
            MbaAcWithstandRow(doi_tuong_thu="Cao – (Hạ + vỏ)", u_thu="50", thoi_gian="1 phút"),
            MbaAcWithstandRow(doi_tuong_thu="Hạ – (Cao + vỏ)", u_thu="3", thoi_gian="1 phút"),
        ]
    )
    thiet_bi_kiem_dinh: str = "Kyoritsu 3125A, C.A 6255, DTR 8510, HVTS-70/50, Multimeter, Variac."
    ket_luan: str = "Máy biến áp 3 pha trên đạt yêu cầu đóng điện vận hành"


# --- 3. Máy cắt hạ thế (MCCB & ACB) ---
class MccbRow(BaseModel):
    stt: str = "1"
    rcd_close: str = ">5000"
    rcd_open: str = ">5000"
    rtx_a: str = "273"
    rtx_b: str = "275"
    rtx_c: str = "279"
    utest: str = "3"
    dong_cat: str = "5"
    ket_qua: str = "Đạt"
    so_tem: str = "017245"


class MccbData(BaseModel):
    hieu: str = "MITSUBISHI"
    so_cuc: str = "03"
    loai: str = "MCCB"
    kieu: str = "NF-250"
    dien_ap_dinh_muc: str = "-"
    dong_dien_dinh_muc: str = "250A"
    dong_ngan_mach: str = "-"
    tan_so: str = "50Hz"
    dien_ap_cach_dien: str = "-"
    dien_ap_xung: str = "-"
    kiem_tra_ben_ngoai: str = "Bình thường"
    so_luong: str = "01"
    rows: List[MccbRow] = Field(default_factory=lambda: [MccbRow()])
    thiet_bi_kiem_dinh: str = "Kyoritsu 3165; Kyoritsu 3125A; CA 6255; CA 6292; HVT-70/50"
    tieu_chuan_kiem_dinh: str = "QCVN QTĐ-5: 2009/BCT; QT/TNMCĐ"
    ket_luan: str = "01 máy cắt hạ thế (MCCB) trên đạt yêu cầu đóng điện vận hành."


# --- 4. Chống sét van (LA) ---
class LaRow(BaseModel):
    doi_tuong_do: str = "LA 01"
    dien_tro_cach_dien: str = ">10000"
    dong_dien_ro: str = "17"
    dien_ap_ac: str = "35"


class LaData(BaseModel):
    vat_lieu_cach_dien: str = "Polymer"
    mcov: str = "15,3kV"
    dien_ap_dinh_muc: str = "18kV"
    tan_so: str = "50Hz"
    dong_dien_xa: str = "10 kA"
    kiem_tra_ben_ngoai: str = "Bình thường"
    so_luong: str = "01"
    rows: List[LaRow] = Field(default_factory=lambda: [LaRow()])
    tieu_chuan_kiem_dinh: str = "QCVN QTĐ-5,6,7: 2009/BCT"
    thiet_bi_kiem_dinh: str = "Kyoritsu 3125A ; HVT-70/50"
    ket_luan: str = "Một (01) chống sét van trên đạt yêu cầu đóng điện vận hành"


# --- 5. Cầu chì tự rơi (FCO & LBFCO) ---
class FcoRow(BaseModel):
    thiet_bi: str = "FCO 01"
    rcd_truoc: str = ">10000"
    rcd_sau: str = ">10000"
    ac_kho: str = "60"
    ac_uot: str = "50"
    dong_cat: str = "5"
    ket_qua: str = "Đạt"


class FcoData(BaseModel):
    vat_lieu_cach_dien: str = "Sứ"
    dong_dien_dinh_muc: str = "100A"
    dien_ap_dinh_muc: str = "27kV"
    kha_nang_cat_ngan_mach: str = "12kA"
    kiem_tra_ben_ngoai: str = "Bình thường"
    so_luong: str = "01"
    rows: List[FcoRow] = Field(default_factory=lambda: [FcoRow()])
    tieu_chuan_kiem_dinh: str = "QCVN QTĐ-5,6,7: 2009/BCT"
    thiet_bi_kiem_dinh: str = "Kyoritsu 3125A; I/IOM 100"
    ket_luan: str = "Một (01) FCO trên đạt yêu cầu đóng điện vận hành"


# --- 6. Điện trở nối đất (ĐTNĐ) ---
class DtndRow(BaseModel):
    stt: str = "1"
    chi_danh: str = "Điện trở nối đất trạm biến áp"
    ket_noi_trung_tinh: str = "Có"
    loai_tiep_dat: str = "Làm việc"
    gia_tri_do: str = "3,52"


class DtndData(BaseModel):
    rows: List[DtndRow] = Field(default_factory=lambda: [DtndRow()])
    thiet_bi_thu_nghiem: str = "KEW 4105DL"
    ghi_chu_1: str = "Chỉ danh, vị trí cọc nối đất do đơn vị yêu cầu thử nghiệm cung cấp"
    ghi_chu_2: str = "Các kết quả đo chỉ có giá trị đối với điểm đo"


# --- 7. Thông tuyến cáp ngầm trung thế ---
class CapInsulationRow(BaseModel):
    doi_tuong_do: str = "Pha 1 – (2+3+vỏ)"
    tieu_chuan: str = ">5000"
    so_lieu_do: str = ">10000"


class CapDcHipotsRow(BaseModel):
    doi_tuong_do: str = "Pha 1 – (2+3+vỏ)"
    thoi_gian: str = "15"
    dien_ap_thu: str = "38,1"
    dong_ro: str = "17"


class CapNgamData(BaseModel):
    so_tem: str = "016139"
    doan_cap_tu: str = "Trụ 82/1"
    doan_cap_den: str = "Trạm biến áp 1500kVA"
    loai_cap: str = "Cáp ngầm trung thế"
    tiet_dien: str = "3 x 50mm2"
    dien_ap_dinh_muc: str = "12,7/22(24)kV"
    tan_so: str = "50Hz"
    kiem_tra_ben_ngoai: str = "Bình thường"
    nhiet_do: str = "34⁰C"
    cach_dien_rows: List[CapInsulationRow] = Field(
        default_factory=lambda: [
            CapInsulationRow(doi_tuong_do="Pha 1 – (2+3+vỏ)", tieu_chuan=">5000", so_lieu_do=">10000"),
            CapInsulationRow(doi_tuong_do="Pha 2 – (1+3+vỏ)", tieu_chuan=">5000", so_lieu_do=">10000"),
            CapInsulationRow(doi_tuong_do="Pha 3 – (1+2+vỏ)", tieu_chuan=">5000", so_lieu_do=">10000"),
        ]
    )
    dc_tang_cao_rows: List[CapDcHipotsRow] = Field(
        default_factory=lambda: [
            CapDcHipotsRow(doi_tuong_do="Pha 1 – (2+3+vỏ)", thoi_gian="15", dien_ap_thu="38,1", dong_ro="17"),
            CapDcHipotsRow(doi_tuong_do="Pha 2 – (1+3+vỏ)", thoi_gian="15", dien_ap_thu="38,1", dong_ro="12"),
            CapDcHipotsRow(doi_tuong_do="Pha 3 – (1+2+vỏ)", thoi_gian="15", dien_ap_thu="38,1", dong_ro="15"),
        ]
    )
    thiet_bi_kiem_dinh: str = "Kyoritsu 3125A, HTV-70/50"
    ket_luan: str = "01 đoạn cáp 3 pha đạt yêu cầu đóng điện vận hành"


# --- 8. Tủ tụ bù hạ thế ---
class TuBuSwitchRow(BaseModel):
    stt: str = "1"
    rcd_close: str = ">5000"
    rcd_open: str = ">5000"
    rtx_a: str = "325"
    rtx_b: str = "329"
    rtx_c: str = "327"
    utest: str = "3"
    dong_cat: str = "5"
    ket_qua: str = "Đạt"


class TuBuCapRow(BaseModel):
    stt: str = "1"
    dung_luong: str = "10"
    r_cach_dien: str = ">2000"
    dien_dung: str = "164,3"
    ket_qua: str = "Đạt"


class TuBuData(BaseModel):
    kiem_tra_ben_ngoai: str = "Bình thường"
    mccb_tong_thong_so: str = "1200A, ABS 1203b, 415V, 65kA, 50Hz"
    mccb_tong_so_luong: str = "01"
    mccb_tong_rows: List[TuBuSwitchRow] = Field(default_factory=lambda: [TuBuSwitchRow()])
    mccb_nhanh_thong_so: str = "200A, ABN 203c, 380V, 30kA, 50Hz"
    mccb_nhanh_so_luong: str = "06"
    mccb_nhanh_rows: List[TuBuSwitchRow] = Field(default_factory=lambda: [TuBuSwitchRow()])
    contactor_thong_so: str = "LS, MC-150a"
    contactor_so_luong: str = "06"
    contactor_rows: List[TuBuSwitchRow] = Field(default_factory=lambda: [TuBuSwitchRow()])
    tu_bu_so_luong: str = "30"
    tu_bu_rows: List[TuBuCapRow] = Field(default_factory=lambda: [TuBuCapRow()])
    thiet_bi_kiem_dinh: str = "Kyoritsu 3165; Kyoritsu 3125A; CA 6255; CA 6292; HVT-70/50; CA 6555; Megger DPM1000."
    tieu_chuan_kiem_dinh: str = "QCVN QTĐ-5: 2009/BCT; QT/TNMCĐ"
    ket_luan: str = "Tủ tụ bù trên đạt yêu cầu đóng điện vận hành"


class ReportDocumentRequest(BaseModel):
    report_type: ReportType
    filename: str = "bien_ban.docx"
    common: CommonHeader = Field(default_factory=CommonHeader)
    signatory: SignatoryInfo = Field(default_factory=SignatoryInfo)
    company: CompanyInfo = Field(default_factory=CompanyInfo)
    data: Dict[str, Any] = Field(default_factory=dict)


class BatchExportRequest(BaseModel):
    zip_filename: str = "Ho_so_kiem_dinh.zip"
    reports: List[ReportDocumentRequest]
