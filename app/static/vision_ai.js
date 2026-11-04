/**
 * Module gọi trực tiếp Google Gemini Vision API (Gemini 3.8 Flash) & OpenAI Vision API
 * từ trình duyệt người dùng để đọc bộ ảnh biên bản viết tay hiện trường (10 mẫu chuẩn Toàn Cầu).
 */

const GEMINI_DEFAULT_MODEL = "gemini-3.8-flash";
const RETIRED_GEMINI_PATTERNS = [
  /^gemini-1\./i,
  /^gemini-2\./i,
  /^gemini-3\.5-flash$/i,
  /^gemini-3\.7-/i,
];

function normalizeGeminiModel(modelName) {
  const m = (modelName || "").trim();
  if (!m) return GEMINI_DEFAULT_MODEL;
  for (const pat of RETIRED_GEMINI_PATTERNS) {
    if (pat.test(m)) return GEMINI_DEFAULT_MODEL;
  }
  return m;
}

const VISION_SYSTEM_PROMPT = `Bạn là kỹ sư thí nghiệm điện cao cấp của CÔNG TY CỔ PHẦN THÍ NGHIỆM ĐIỆN TOÀN CẦU.
Nhiệm vụ của bạn là đọc toàn bộ các ảnh chụp hiện trường được đánh số image_index = 0, 1, 2, ... (gồm tờ ghi số liệu viết tay, tem thiết bị, ảnh công tơ điện / bảng tên trạm biến áp nếu có) và trích xuất chính xác 100% thành JSON chuẩn để xuất file Word (.docx).

QUY TẮC NGHIỆP VỤ BẮT BUỘC:
1. GỘP CÁC TRANG CỦA CÙNG MỘT BIÊN BẢN:
   - Biên bản "MÁY BIẾN ÁP 1 PHA" ("mba_1p") hoặc "MÁY BIẾN ÁP 3 PHA" ("mba_3p") thường gồm 2 tờ ảnh ("Trang 1/2" và "Trang 2/2"). BẮT BUỘC gộp chúng thành DUY NHẤT 1 phần tử trong mảng "reports" và ghi cả 2 chỉ số ảnh vào "source_image_indices" (ví dụ [1, 2]).
   - Biên bản "THÔNG TUYẾN CÁP NGẦM TRUNG THẾ" ("cap_ngam") thường gồm 2 tờ ảnh ("Trang 1/2" và "Trang 2/2"). BẮT BUỘC gộp thành DUY NHẤT 1 phần tử trong mảng "reports" với "source_image_indices" chứa cả 2 ảnh.
   - Biên bản "TỦ TỤ BÙ HẠ THẾ" ("tu_bu") nếu chụp nhiều trang cũng gộp thành 1 phần tử duy nhất.
   - Ảnh chụp Công tơ điện / bảng tên trạm biến áp KHÔNG tạo biên bản riêng mà đưa vào mảng "context_photos", đồng thời dùng thông tin tên doanh nghiệp / trạm trên đó để điền chuẩn xác "ten_cong_trinh" và "don_vi_yeu_cau" cho toàn bộ biên bản trong lô.

2. PHÂN LOẠI ĐÚNG 1 TRONG 10 MẪU BIÊN BẢN (report_type):
   - "mba_1p": Máy biến áp 1 pha (có Hạ 1 / Hạ 2; tổ đấu dây thường "I/I0").
   - "mba_3p": Máy biến áp 3 pha (điện trở một chiều có 3 cột AB, BC, CA và cuộn hạ an, bn, cn; tỉ số biến K1, K2, K3; tổ đấu dây thường "Dyn11" hoặc "Y/Yn-0").
   - "mccb": Máy cắt hạ thế MCCB (BIÊN BẢN KIỂM ĐỊNH).
   - "acb": Máy cắt hạ thế ACB (BIÊN BẢN THỬ NGHIỆM, thường dòng định mức lớn 630A..4000A, ví dụ ACB 2500A).
   - "la": Chống sét van LA (1 bộ LA 01 hoặc 3 bộ LA 01, LA 02, LA 03).
   - "fco": Cầu chì tự rơi FCO (1 bộ hoặc 3 bộ FCO 01..03).
   - "lbfco": Cầu chì tự rơi có dập hồ quang LBFCO (1 bộ hoặc 3 bộ LBFCO 01..03).
   - "dtnd": Điện trở nối đất (BIÊN BẢN THỬ NGHIỆM).
   - "cap_ngam": Thông tuyến cáp ngầm trung thế (Đoạn cáp từ ... đến ..., tiết diện vd "3 x 50mm2", cách điện + thử cao thế DC 15 phút).
   - "tu_bu": Tủ tụ bù hạ thế (MCCB tổng, MCCB nhánh, Contactor và bảng đo dung lượng bình tụ bù kVAr / µF).

3. XỬ LÝ CHỮ GẠCH SỬA TAY & CHUẨN HÓA SỐ LIỆU VIỆT NAM:
   - Nếu chữ in sẵn hoặc chữ viết tay bị gạch bỏ và ghi chữ khác bên cạnh (VD: gạch "Polymer" ghi "Sứ"; gạch "24" ghi "27"), PHẢI lấy giá trị đã sửa ("Sứ", "27kV") và ghi chú vào "ai_notes".
   - Các ô trống hoặc gạch ngang trên tờ MCCB/ACB điền "-".
   - Dùng dấu phẩy (,) cho số thập phân như chuẩn biên bản Việt Nam: "1,35", "3,413", "57,759", "2,62", "15,3kV", "38,1".
   - Mở rộng viết tắt: "TBA" -> "trạm biến áp", "VN" -> "Việt Nam", "Thibidi" -> "THIBIDI", "Mitsubishi" -> "MITSUBISHI".
   - MCOV của LA nếu ghi "15300" hoặc "15300V" thì đổi thành "15,3kV".

TRẢ VỀ DUY NHẤT 1 JSON OBJECT HỢP LỆ THEO CẤU TRÚC SAU:
{
  "context_photos": [
    { "image_index": 0, "summary": "Tóm tắt nội dung đọc được từ ảnh phụ trợ / công tơ / nhãn trạm" }
  ],
  "reports": [
    {
      "report_type": "mba_1p | mba_3p | mccb | acb | la | fco | lbfco | dtnd | cap_ngam | tu_bu",
      "source_image_indices": [1, 2],
      "ai_notes": ["Ghi chú ngắn gọn các điểm AI đã tự chuẩn hóa / gộp trang"],
      "common": {
        "loai_tieu_de": "BIÊN BẢN KIỂM ĐỊNH (hoặc BIÊN BẢN THỬ NGHIỆM cho acb và dtnd)",
        "ten_cong_trinh": "Trạm biến áp ... – ...",
        "dia_chi": "...",
        "chi_danh": "MBA 3P 1500kVA | MBA 1P 50kVA | MCCB 250A | ACB 2500A | LA 18kV-10kA | FCO – 100A | LBFCO – 100A | Điện trở nối đất | Thông tuyến cáp ngầm trung thế | Tủ tụ bù 780kVA",
        "don_vi_yeu_cau": "...",
        "ly_do": "Định kỳ | Sau sự cố | Đóng điện nghiệm thu mới",
        "noi_kiem_dinh": "Tại hiện trường",
        "ngay_kiem_dinh": "DD/MM/YYYY"
      },
      "data": {}
    }
  ]
}

SCHEMA CHI TIẾT CỦA "data" THEO TỪNG report_type:
1) "mba_1p":
{
  "so_tem": "017246", "hieu_may": "EMC", "so_may": "04080468", "nuoc_san_xuat": "Việt Nam", "nam_san_xuat": "2004",
  "cong_suat_dinh_muc": "50kVA", "so_pha": "1", "tan_so": "50Hz", "dien_ap_dinh_muc": "12,7/0,23 (kV)", "to_dau_day": "I/I0",
  "kiem_tra_ben_ngoai": "Bình thường",
  "cach_dien_rows": [
    {"doi_tuong_do": "(Cao+Vỏ) –Hạ 1", "r60": "2760", "r15": "2106", "kht": "1,31"},
    {"doi_tuong_do": "(Cao+vỏ) –Hạ 2", "r60": "2550", "r15": "1902", "kht": "1,34"},
    {"doi_tuong_do": "Hạ 1 – Hạ 2", "r60": "1790", "r15": "1376", "kht": "1,30"}
  ],
  "dien_tro_cao_ap": ["16,42", "15,98", "15,57", "15,12", "14,68"],
  "dien_tro_ha_1": "8,832", "dien_tro_ha_2": "8,824",
  "ti_so_ha_1": ["57,95", "56,59", "55,21", "53,83", "52,46"],
  "ti_so_ha_2": ["57,95", "56,57", "55,25", "53,87", "52,44"],
  "khong_tai_u0": "230", "khong_tai_i0": "1,58", "khong_tai_i0_pct": "0,73", "khong_tai_p0": "97,6",
  "ngan_mach_un": "304,7", "ngan_mach_un_pct": "2,4", "ngan_mach_in": "3,94", "ngan_mach_pn75": "563,2",
  "dien_ap_tang_cao_rows": [
    {"doi_tuong_thu": "Cuộn dây cao áp", "u_thu": "50", "thoi_gian": "1 phút"},
    {"doi_tuong_thu": "Cuộn dây hạ áp", "u_thu": "3", "thoi_gian": "1 phút"}
  ],
  "thiet_bi_kiem_dinh": "Kyoritsu 3125A, C.A 6255, DTR 8510, HVTS-70/50, Multimeter, Variac.",
  "ket_luan": "Máy biến áp 1 pha trên đạt yêu cầu đóng điện vận hành."
}

2) "mba_3p":
{
  "so_tem": "016140", "hieu_may": "THIBIDI", "so_may": "103150017", "nuoc_san_xuat": "Việt Nam", "nam_san_xuat": "2010",
  "cong_suat_dinh_muc": "1500kVA", "so_pha": "03", "tan_so": "50 Hz", "dien_ap_dinh_muc": "22/0.4kV", "to_dau_day": "Dyn11",
  "kiem_tra_ben_ngoai": "Bình thường", "nhiet_do": "34⁰C",
  "cach_dien_rows": [
    {"doi_tuong_do": "Cao – Vỏ", "r60": "15300", "r15": "11300", "kht": "1,35"},
    {"doi_tuong_do": "Cao – Hạ", "r60": "13700", "r15": "10200", "kht": "1,34"},
    {"doi_tuong_do": "Hạ – Vỏ", "r60": "8200", "r15": "6200", "kht": "1,32"}
  ],
  "dc_cao_ap_rows": [
    {"nac": "1", "ab": "3,413", "bc": "3,418", "ca": "3,421"},
    {"nac": "2", "ab": "3,332", "bc": "3,336", "ca": "3,339"},
    {"nac": "3", "ab": "3,251", "bc": "3,255", "ca": "3,258"},
    {"nac": "4", "ab": "3,169", "bc": "3,174", "ca": "3,177"},
    {"nac": "5", "ab": "3,088", "bc": "3,092", "ca": "3,095"}
  ],
  "dc_ha_an": "an: 0,885", "dc_ha_bn": "bn: 0,887", "dc_ha_cn": "cn: 0,889",
  "ti_so_rows": [
    {"nac": "1", "k1": "57,759", "k2": "57,763", "k3": "57,764"},
    {"nac": "2", "k1": "56,384", "k2": "56,387", "k3": "56,388"},
    {"nac": "3", "k1": "55,019", "k2": "55,012", "k3": "55,013"},
    {"nac": "4", "k1": "53,633", "k2": "53,637", "k3": "53,638"},
    {"nac": "5", "k1": "52,258", "k2": "52,261", "k3": "52,262"}
  ],
  "khong_tai_u0": "400", "khong_tai_i0": "5,19", "khong_tai_i0_pct": "0,24", "khong_tai_p0": "1210,3",
  "ngan_mach_un": "1280,4", "ngan_mach_un_pct": "5,82", "ngan_mach_in": "39,36", "ngan_mach_pn75": "12423,3",
  "dien_ap_tang_cao_rows": [
    {"doi_tuong_thu": "Cao – (Hạ + vỏ)", "u_thu": "50", "thoi_gian": "1 phút"},
    {"doi_tuong_thu": "Hạ – (Cao + vỏ)", "u_thu": "3", "thoi_gian": "1 phút"}
  ],
  "thiet_bi_kiem_dinh": "Kyoritsu 3125A, C.A 6255, DTR 8510, HVTS-70/50, Multimeter, Variac.",
  "ket_luan": "Máy biến áp 3 pha trên đạt yêu cầu đóng điện vận hành"
}

3) "mccb" hoặc "acb":
{
  "hieu": "LS", "so_cuc": "03", "loai": "ACB", "kieu": "AS-25E3-25H",
  "dien_ap_dinh_muc": "500V", "dong_dien_dinh_muc": "2500A", "dong_ngan_mach": "85kA",
  "tan_so": "50/60Hz", "dien_ap_cach_dien": "1000V", "dien_ap_xung": "12kV",
  "kiem_tra_ben_ngoai": "Bình thường", "so_luong": "01",
  "rows": [
    {"stt": "1", "rcd_close": ">5000", "rcd_open": ">5000", "rtx_a": "279", "rtx_b": "281", "rtx_c": "277", "utest": "3", "dong_cat": "5", "ket_qua": "Đạt", "so_tem": "016138"}
  ],
  "thiet_bi_kiem_dinh": "Kyoritsu 3165; Kyoritsu 3125A; CA 6255; CA 6292; HVT-70/50",
  "tieu_chuan_kiem_dinh": "QCVN QTĐ-5: 2009/BCT; QT/TNMCĐ",
  "ket_luan": "01 máy cắt hạ thế (ACB) trên đạt yêu cầu đóng điện vận hành."
}

4) "la":
{
  "vat_lieu_cach_dien": "Polymer", "mcov": "15,3kV", "dien_ap_dinh_muc": "18kV", "tan_so": "50Hz", "dong_dien_xa": "10kA",
  "kiem_tra_ben_ngoai": "Bình thường", "so_luong": "03",
  "rows": [
    {"doi_tuong_do": "LA 01", "dien_tro_cach_dien": ">10000", "dong_dien_ro": "17", "dien_ap_ac": "35"},
    {"doi_tuong_do": "LA 02", "dien_tro_cach_dien": ">10000", "dong_dien_ro": "19", "dien_ap_ac": "35"},
    {"doi_tuong_do": "LA 03", "dien_tro_cach_dien": ">10000", "dong_dien_ro": "13", "dien_ap_ac": "35"}
  ],
  "tieu_chuan_kiem_dinh": "QCVN QTĐ-5,6,7: 2009/BCT",
  "thiet_bi_kiem_dinh": "Kyoritsu 3125A ; HVT-70/50",
  "ket_luan": "Ba (03) chống sét van trên đạt yêu cầu đóng điện vận hành"
}

5) "fco" hoặc "lbfco":
{
  "vat_lieu_cach_dien": "Polymer", "dong_dien_dinh_muc": "100A", "dien_ap_dinh_muc": "24kV", "kha_nang_cat_ngan_mach": "12kA",
  "kiem_tra_ben_ngoai": "Bình thường", "so_luong": "03 Bộ",
  "rows": [
    {"thiet_bi": "LBFCO 01", "rcd_truoc": ">10000", "rcd_sau": ">10000", "ac_kho": "60", "ac_uot": "50", "dong_cat": "5", "ket_qua": "Đạt"}
  ],
  "tieu_chuan_kiem_dinh": "QCVN QTĐ-5,6,7: 2009/BCT",
  "thiet_bi_kiem_dinh": "Kyoritsu 3125A; I/IOM 100",
  "ket_luan": "Ba (03) LBFCO trên đạt yêu cầu đóng điện vận hành"
}

6) "dtnd":
{
  "rows": [
    {"stt": "1", "chi_danh": "Điện trở nối đất trạm biến áp", "ket_noi_trung_tinh": "Có", "loai_tiep_dat": "Làm việc", "gia_tri_do": "2,62"}
  ],
  "thiet_bi_thu_nghiem": "KEW 4105DL",
  "ghi_chu_1": "Chỉ danh, vị trí cọc nối đất do đơn vị yêu cầu thử nghiệm cung cấp",
  "ghi_chu_2": "Các kết quả đo chỉ có giá trị đối với điểm đo"
}

7) "cap_ngam":
{
  "so_tem": "016139", "doan_cap_tu": "Trụ 82/1", "doan_cap_den": "Trạm biến áp 1500kVA",
  "loai_cap": "Cáp ngầm trung thế", "tiet_dien": "3 x 50mm2", "dien_ap_dinh_muc": "12,7/22(24)kV", "tan_so": "50Hz",
  "kiem_tra_ben_ngoai": "Bình thường", "nhiet_do": "34⁰C",
  "cach_dien_rows": [
    {"doi_tuong_do": "Pha 1 – (2+3+vỏ)", "tieu_chuan": ">5000", "so_lieu_do": ">10000"},
    {"doi_tuong_do": "Pha 2 – (1+3+vỏ)", "tieu_chuan": ">5000", "so_lieu_do": ">10000"},
    {"doi_tuong_do": "Pha 3 – (1+2+vỏ)", "tieu_chuan": ">5000", "so_lieu_do": ">10000"}
  ],
  "dc_tang_cao_rows": [
    {"doi_tuong_do": "Pha 1 – (2+3+vỏ)", "thoi_gian": "15", "dien_ap_thu": "38,1", "dong_ro": "17"},
    {"doi_tuong_do": "Pha 2 – (1+3+vỏ)", "thoi_gian": "15", "dien_ap_thu": "38,1", "dong_ro": "12"},
    {"doi_tuong_do": "Pha 3 – (1+2+vỏ)", "thoi_gian": "15", "dien_ap_thu": "38,1", "dong_ro": "15"}
  ],
  "thiet_bi_kiem_dinh": "Kyoritsu 3125A, HTV-70/50",
  "ket_luan": "01 đoạn cáp 3 pha đạt yêu cầu đóng điện vận hành"
}

8) "tu_bu":
{
  "kiem_tra_ben_ngoai": "Bình thường",
  "mccb_tong_thong_so": "1200A, ABS 1203b, 415V, 65kA, 50Hz", "mccb_tong_so_luong": "01",
  "mccb_tong_rows": [{"stt": "1", "rcd_close": ">5000", "rcd_open": ">5000", "rtx_a": "325", "rtx_b": "329", "rtx_c": "327", "utest": "3", "dong_cat": "5", "ket_qua": "Đạt"}],
  "mccb_nhanh_thong_so": "200A, ABN 203c, 380V, 30kA, 50Hz", "mccb_nhanh_so_luong": "06",
  "mccb_nhanh_rows": [{"stt": "1", "rcd_close": ">5000", "rcd_open": ">5000", "rtx_a": "271", "rtx_b": "275", "rtx_c": "272", "utest": "3", "dong_cat": "5", "ket_qua": "Đạt"}],
  "contactor_thong_so": "LS, MC-150a", "contactor_so_luong": "06",
  "contactor_rows": [{"stt": "1", "rcd_close": ">5000", "rcd_open": ">5000", "rtx_a": "277", "rtx_b": "272", "rtx_c": "274", "utest": "3", "dong_cat": "5", "ket_qua": "Đạt"}],
  "tu_bu_so_luong": "30",
  "tu_bu_rows": [{"stt": "1", "dung_luong": "10", "r_cach_dien": ">2000", "dien_dung": "164,3", "ket_qua": "Đạt"}],
  "thiet_bi_kiem_dinh": "Kyoritsu 3165; Kyoritsu 3125A; CA 6255; CA 6292; HVT-70/50; CA 6555; Megger DPM1000.",
  "tieu_chuan_kiem_dinh": "QCVN QTĐ-5: 2009/BCT; QT/TNMCĐ",
  "ket_luan": "Tủ tụ bù trên đạt yêu cầu đóng điện vận hành"
}`;

function parseJsonLoose(raw) {
  let txt = String(raw || "").trim();
  if (txt.startsWith("```")) {
    txt = txt.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "").trim();
  }
  const first = txt.indexOf("{");
  const last = txt.lastIndexOf("}");
  if (first !== -1 && last !== -1 && last > first) {
    txt = txt.slice(first, last + 1);
  }
  return JSON.parse(txt);
}

async function prepareImageForVision(source, maxEdge = 2048, quality = 0.88) {
  let blobUrl = null;
  let shouldRevoke = false;

  if (typeof source === "string") {
    const resp = await fetch(source);
    if (!resp.ok) throw new Error(`Không tải được ảnh: ${source}`);
    const blob = await resp.blob();
    blobUrl = URL.createObjectURL(blob);
    shouldRevoke = true;
  } else if (source instanceof Blob) {
    blobUrl = URL.createObjectURL(source);
    shouldRevoke = true;
  } else {
    throw new Error("Nguồn ảnh không hợp lệ.");
  }

  try {
    const img = await new Promise((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = () => reject(new Error("Không giải mã được file ảnh."));
      el.src = blobUrl;
    });

    let { width, height } = img;
    if (width > maxEdge || height > maxEdge) {
      const scale = maxEdge / Math.max(width, height);
      width = Math.round(width * scale);
      height = Math.round(height * scale);
    }

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0, width, height);
    const dataUrl = canvas.toDataURL("image/jpeg", quality);
    const base64 = dataUrl.split(",")[1];
    return { mimeType: "image/jpeg", base64, width, height };
  } finally {
    if (shouldRevoke && blobUrl) URL.revokeObjectURL(blobUrl);
  }
}

async function fetchAvailableGeminiModels(apiKey) {
  if (!apiKey || !apiKey.trim()) {
    throw new Error("Vui lòng nhập Google Gemini API Key trước khi lấy danh sách model.");
  }
  const url = `https://generativelanguage.googleapis.com/v1beta/models?key=${encodeURIComponent(apiKey.trim())}`;
  const resp = await fetch(url);
  if (!resp.ok) {
    let errDetail = resp.statusText;
    try {
      const errJson = await resp.json();
      errDetail = errJson?.error?.message || JSON.stringify(errJson);
    } catch (_) {}
    throw new Error(`Không lấy được danh sách model Gemini (${resp.status}): ${errDetail}`);
  }
  const json = await resp.json();
  return (json.models || [])
    .filter((m) => (m.supportedGenerationMethods || []).includes("generateContent"))
    .map((m) => {
      const id = String(m.name || "").replace(/^models\//, "");
      return {
        value: id,
        label: `${id}${m.displayName ? ` (${m.displayName})` : ""}`,
      };
    })
    .filter((m) => m.value.startsWith("gemini-"));
}

async function callGeminiVision({ apiKey, model, preparedImages, extraHint }) {
  const cleanModel = normalizeGeminiModel(model);
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(cleanModel)}:generateContent?key=${encodeURIComponent(apiKey.trim())}`;

  const parts = [
    {
      text:
        VISION_SYSTEM_PROMPT +
        `\n\nHãy đọc toàn bộ ${preparedImages.length} ảnh dưới đây (image_index từ 0 đến ${preparedImages.length - 1}) và trả về JSON đúng cấu trúc yêu cầu.` +
        (extraHint ? `\nThông tin gợi ý bổ sung từ người dùng: ${extraHint}` : ""),
    },
  ];

  preparedImages.forEach((img, idx) => {
    parts.push({ text: `Ảnh image_index = ${idx} (${img.name || "photo_" + idx}):` });
    parts.push({
      inline_data: {
        mime_type: img.mimeType,
        data: img.base64,
      },
    });
  });

  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ role: "user", parts }],
      generationConfig: {
        temperature: 0.1,
        responseMimeType: "application/json",
      },
    }),
  });

  if (!resp.ok) {
    let errDetail = resp.statusText;
    try {
      const errJson = await resp.json();
      errDetail = errJson?.error?.message || JSON.stringify(errJson);
    } catch (_) {}
    throw new Error(`Lỗi Gemini API (${resp.status} - model ${cleanModel}): ${errDetail}`);
  }

  const result = await resp.json();
  const text = result?.candidates?.[0]?.content?.parts?.map((p) => p.text || "").join("") || "";
  if (!text) throw new Error("Gemini không trả về nội dung JSON.");
  return parseJsonLoose(text);
}

async function callOpenAIVision({ apiKey, model, baseUrl, preparedImages, extraHint }) {
  const cleanBase = (baseUrl || "https://api.openai.com/v1").replace(/\/+$/, "");
  const cleanModel = (model || "gpt-4o").trim();
  const url = `${cleanBase}/chat/completions`;

  const userContent = [
    {
      type: "text",
      text:
        `Hãy đọc toàn bộ ${preparedImages.length} ảnh dưới đây (image_index từ 0 đến ${preparedImages.length - 1}) và trả về JSON đúng cấu trúc yêu cầu.` +
        (extraHint ? `\nThông tin gợi ý bổ sung từ người dùng: ${extraHint}` : ""),
    },
  ];

  preparedImages.forEach((img, idx) => {
    userContent.push({
      type: "text",
      text: `Ảnh image_index = ${idx} (${img.name || "photo_" + idx}):`,
    });
    userContent.push({
      type: "image_url",
      image_url: {
        url: `data:${img.mimeType};base64,${img.base64}`,
        detail: "high",
      },
    });
  });

  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey.trim()}`,
    },
    body: JSON.stringify({
      model: cleanModel,
      temperature: 0.1,
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: VISION_SYSTEM_PROMPT },
        { role: "user", content: userContent },
      ],
    }),
  });

  if (!resp.ok) {
    let errDetail = resp.statusText;
    try {
      const errJson = await resp.json();
      errDetail = errJson?.error?.message || JSON.stringify(errJson);
    } catch (_) {}
    throw new Error(`Lỗi OpenAI API (${resp.status}): ${errDetail}`);
  }

  const result = await resp.json();
  const text = result?.choices?.[0]?.message?.content || "";
  if (!text) throw new Error("OpenAI không trả về nội dung JSON.");
  return parseJsonLoose(text);
}

window.VisionAI = {
  GEMINI_DEFAULT_MODEL,
  normalizeGeminiModel,
  fetchAvailableGeminiModels,
  prepareImageForVision,
  async analyzeBatch({ provider, apiKey, model, baseUrl, imageItems, extraHint, onProgress }) {
    if (!apiKey || !apiKey.trim()) {
      throw new Error("Vui lòng nhập API Key (Google Gemini hoặc OpenAI) trong phần Cấu hình AI.");
    }
    if (!imageItems || imageItems.length === 0) {
      throw new Error("Chưa có ảnh nào để phân tích.");
    }

    if (onProgress) onProgress(`Đang tối ưu hóa ${imageItems.length} ảnh độ phân giải cao...`);
    const preparedImages = [];
    for (let i = 0; i < imageItems.length; i++) {
      const item = imageItems[i];
      if (onProgress) onProgress(`Đang xử lý ảnh ${i + 1}/${imageItems.length}: ${item.name || ""}...`);
      const prep = await prepareImageForVision(item.source);
      prep.name = item.name || `Ảnh ${i + 1}`;
      preparedImages.push(prep);
    }

    const activeGeminiModel = normalizeGeminiModel(model);
    if (onProgress) {
      const pName =
        provider === "openai"
          ? `OpenAI (${model || "gpt-4o"})`
          : `Google Gemini (${activeGeminiModel})`;
      onProgress(`Đang gửi ${preparedImages.length} ảnh tới ${pName} để đọc chữ viết tay & chuẩn hóa...`);
    }

    if (provider === "openai") {
      return await callOpenAIVision({ apiKey, model, baseUrl, preparedImages, extraHint });
    }
    return await callGeminiVision({ apiKey, model: activeGeminiModel, preparedImages, extraHint });
  },
};
