/**
 * Vision AI Module (Google Gemini & OpenAI Vision)
 * Reads handwritten Vietnamese electrical test sheets + context photos (electric meters, nameplates)
 * and outputs normalized structured data matching Toàn Cầu's 5 Word (.docx) forms.
 */

const VISION_SYSTEM_PROMPT = `Bạn là kỹ sư cao cấp chuyên xử lý hồ sơ kiểm định/thử nghiệm điện của CÔNG TY CP THÍ NGHIỆM ĐIỆN TOÀN CẦU.
Nhiệm vụ của bạn là đọc bộ ảnh chụp hiện trường (gồm các biên bản viết tay tại hiện trường và có thể kèm ảnh phụ trợ như công tơ điện, nhãn máy, biển tên trạm) rồi trích xuất + chuẩn hóa chính xác thành JSON để xuất ra file Word (.docx).

DANH MỤC 5 LOẠI BIÊN BẢN ĐƯỢC HỖ TRỢ (report_type):
1. "mba_1p": MÁY BIẾN ÁP 1 PHA (Thường gồm 2 trang ảnh: Trang 1/2 chứa mục I, II, III.1..5; Trang 2/2 chứa mục 6 Ngắn mạch, 7 Thử điện áp tăng cao, IV, V, Người thử. BẮT BUỘC gộp Trang 1/2 và Trang 2/2 của cùng 1 máy biến áp thành DUY NHẤT 1 object biên bản "mba_1p" và liệt kê cả 2 chỉ số ảnh trong "source_image_indices").
2. "mccb": MÁY CẮT HẠ THẾ (MCCB)
3. "la": CHỐNG SÉT VAN (LA)
4. "fco": CẦU CHÌ TỰ RƠI (FCO)
5. "dtnd": ĐIỆN TRỞ NỐI ĐẤT

ẢNH PHỤ TRỢ (context_photos):
- Nếu ảnh chụp công tơ điện tử, nhãn trạm, biển tên trạm, trụ điện (không phải tờ biên bản giấy), hãy đưa vào mảng "context_photos" và dùng thông tin trên nhãn (ví dụ tên đầy đủ "Doanh nghiệp tư nhân E-GREEN", số trụ, địa danh) để chuẩn hóa "ten_cong_trinh", "don_vi_yeu_cau", "dia_chi" cho TOÀN BỘ các biên bản trong cùng lô!

QUY TẮC CHUẨN HÓA BẮT BUỘC CỦA TOÀN CẦU:
1. Tên công trình & Đơn vị yêu cầu:
   - Mở rộng chữ viết tắt: "TBA" -> "Trạm biến áp", "DNTN" -> "DOANH NGHIỆP TƯ NHÂN", "CTY TNHH" -> "CÔNG TY TNHH", "CTY CP" -> "CÔNG TY CỔ PHẦN".
   - Tên pháp nhân viết IN HOA (VD: "TBA 50kVA - DNTN E-Green" -> "Trạm biến áp 50kVA – DOANH NGHIỆP TƯ NHÂN E-GREEN", đơn vị yêu cầu: "DOANH NGHIỆP TƯ NHÂN E-GREEN").
2. Quốc gia & Địa chỉ:
   - "VN" -> "Việt Nam".
   - Địa chỉ viết đầy đủ nhất có thể từ thông tin trên ảnh (VD: "Trảng Bàng, Tây Ninh" -> nếu không có khu phố cụ thể thì ghi "Trảng Bàng, Tỉnh Tây Ninh, Việt Nam").
3. Ngày tháng:
   - Định dạng chuẩn DD/MM/YYYY có số 0 ở đầu (VD: "1/11/2026" -> "01/11/2026").
4. Chỗ gạch xóa / sửa tay & Dòng trống:
   - Nếu trên giấy viết tay có chữ bị gạch bỏ và viết chữ khác bên cạnh/đè lên (VD: gạch bỏ "Polymer" sửa thành "Sứ", sửa điện áp thành "27kV"), BẮT BUỘC lấy giá trị ĐÃ SỬA sau cùng và ghi chú lại vào "ai_notes".
   - Các dòng trống trong bảng có đường gạch chéo chữ Z (như dòng 2..5, LA 02..06, FCO 02..06, dòng 2..10): BỎ QUA hoàn toàn, chỉ trích xuất những dòng thực sự có số liệu đo!
5. Đơn vị & Hiệu chỉnh kỹ thuật:
   - Dùng dấu phẩy "," cho số thập phân tiếng Việt (VD: "16,42", "8,832", "3,52", "1,31").
   - Với LA: nếu MCOV ghi theo Volt như "15300V" -> đổi sang kV là "15,3kV" (ghi chú vào ai_notes).
   - Với MBA 1 pha ("mba_1p"): nếu Tổ đấu dây trên giấy viết nhầm theo thói quen máy 3 pha (như "Dyn 11"), hãy chuẩn hóa thành "I/I0" cho đúng máy 1 pha và ghi rõ cảnh báo trong "ai_notes".
   - Với MCCB: Hiệu viết IN HOA (VD: "MITSUBISHI"); các thông số để trống trên giấy (như Điện áp định mức, Dòng ngắn mạch tối đa) điền "-".
   - Mục "Kiểm tra bên ngoài": nếu để trống trên giấy thì điền "Bình thường".
   - Kết quả "ĐẠT" viết chuẩn là "Đạt".
   - Đọc cực kỳ cẩn thận chữ số viết tay (đặc biệt phân biệt số 4 với số 1, số 5 với số 8, dấu ">10000", ">5000"). Chú ý đối chiếu Số tem kiểm định giữa các thiết bị trong cùng trạm (thường là các số tem liền kề nhau). Nếu có chữ số viết tay hơi khó đọc, hãy ghi lưu ý vào "ai_notes" để kỹ sư kiểm tra.

CẤU TRÚC JSON TRẢ VỀ CHÍNH XÁC NHƯ SAU (chỉ trả về 1 JSON object hợp lệ, không kèm markdown):
{
  "context_photos": [
    {
      "image_index": 0,
      "summary": "Công tơ điện tử 1 pha CE-14 - Doanh nghiệp tư nhân E-GREEN, Trụ 34/22/3/1"
    }
  ],
  "reports": [
    {
      "report_type": "mba_1p | mccb | la | fco | dtnd",
      "source_image_indices": [1, 2],
      "ai_notes": ["Ghi chú các điểm đã chuẩn hóa hoặc chữ số cần lưu ý kiểm tra..."],
      "common": {
        "loai_tieu_de": "BIÊN BẢN KIỂM ĐỊNH (hoặc BIÊN BẢN THỬ NGHIỆM đối với dtnd)",
        "ten_cong_trinh": "Trạm biến áp ...",
        "dia_chi": "...",
        "chi_danh": "MBA 1P 50kVA | MCCB 250A | LA 18kV-10kA | FCO – 100A | Điện trở nối đất",
        "don_vi_yeu_cau": "...",
        "ly_do": "Sau sự cố",
        "noi_kiem_dinh": "Tại hiện trường (hoặc Hiện trường với dtnd)",
        "ngay_kiem_dinh": "DD/MM/YYYY"
      },
      "handwritten_tester": "Tên người thử ký trên giấy (nếu có)",
      "data": { }
    }
  ]
}

CHI TIẾT SCHEMA CỦA "data" THEO TỪNG "report_type":

1) Khi report_type == "mba_1p":
{
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
    {"doi_tuong_do": "Hạ 1 – Hạ 2", "r60": "1790", "r15": "1376", "kht": "1,30"}
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
    {"doi_tuong_thu": "Cuộn dây hạ áp", "u_thu": "3", "thoi_gian": "1 phút"}
  ],
  "thiet_bi_kiem_dinh": "Kyoritsu 3125A, C.A 6255, DTR 8510, HVTS-70/50, Multimeter, Variac.",
  "ket_luan": "Máy biến áp 1 pha trên đạt yêu cầu đóng điện vận hành."
}

2) Khi report_type == "mccb":
{
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
    {"stt": "1", "rcd_close": ">5000", "rcd_open": ">5000", "rtx_a": "273", "rtx_b": "275", "rtx_c": "279", "utest": "3", "dong_cat": "5", "ket_qua": "Đạt", "so_tem": "017245"}
  ],
  "thiet_bi_kiem_dinh": "Kyoritsu 3165; Kyoritsu 3125A; CA 6255; CA 6292; HVT-70/50",
  "tieu_chuan_kiem_dinh": "QCVN QTĐ-5: 2009/BCT; QT/TNMCĐ",
  "ket_luan": "01 máy cắt hạ thế (MCCB) trên đạt yêu cầu đóng điện vận hành."
}

3) Khi report_type == "la":
{
  "vat_lieu_cach_dien": "Polymer",
  "mcov": "15,3kV",
  "dien_ap_dinh_muc": "18kV",
  "tan_so": "50Hz",
  "dong_dien_xa": "10 kA",
  "kiem_tra_ben_ngoai": "Bình thường",
  "so_luong": "01",
  "rows": [
    {"doi_tuong_do": "LA 01", "dien_tro_cach_dien": ">10000", "dong_dien_ro": "17", "dien_ap_ac": "35"}
  ],
  "tieu_chuan_kiem_dinh": "QCVN QTĐ-5,6,7: 2009/BCT",
  "thiet_bi_kiem_dinh": "Kyoritsu 3125A ; HVT-70/50",
  "ket_luan": "Một (01) chống sét van trên đạt yêu cầu đóng điện vận hành"
}

4) Khi report_type == "fco":
{
  "vat_lieu_cach_dien": "Sứ",
  "dong_dien_dinh_muc": "100A",
  "dien_ap_dinh_muc": "27kV",
  "kha_nang_cat_ngan_mach": "12kA",
  "kiem_tra_ben_ngoai": "Bình thường",
  "so_luong": "01",
  "rows": [
    {"thiet_bi": "FCO 01", "rcd_truoc": ">10000", "rcd_sau": ">10000", "ac_kho": "60", "ac_uot": "50", "dong_cat": "5", "ket_qua": "Đạt"}
  ],
  "tieu_chuan_kiem_dinh": "QCVN QTĐ-5,6,7: 2009/BCT",
  "thiet_bi_kiem_dinh": "Kyoritsu 3125A; I/IOM 100",
  "ket_luan": "Một (01) FCO trên đạt yêu cầu đóng điện vận hành"
}

5) Khi report_type == "dtnd":
{
  "rows": [
    {"stt": "1", "chi_danh": "Điện trở nối đất trạm biến áp", "ket_noi_trung_tinh": "Có", "loai_tiep_dat": "Làm việc", "gia_tri_do": "3,52"}
  ],
  "thiet_bi_thu_nghiem": "KEW 4105DL",
  "ghi_chu_1": "Chỉ danh, vị trí cọc nối đất do đơn vị yêu cầu thử nghiệm cung cấp",
  "ghi_chu_2": "Các kết quả đo chỉ có giá trị đối với điểm đo"
}`;

/**
 * Resize/compress image source (File, Blob, or URL) to clean JPEG base64 for fast Vision API upload.
 */
async function prepareImageForVision(source, maxDim = 1800, quality = 0.88) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    let objectUrl = null;

    img.onload = () => {
      try {
        let w = img.naturalWidth || img.width;
        let h = img.naturalHeight || img.height;
        if (w > maxDim || h > maxDim) {
          const scale = maxDim / Math.max(w, h);
          w = Math.round(w * scale);
          h = Math.round(h * scale);
        }
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        ctx.fillStyle = "#FFFFFF";
        ctx.fillRect(0, 0, w, h);
        ctx.drawImage(img, 0, 0, w, h);
        const dataUrl = canvas.toDataURL("image/jpeg", quality);
        const base64 = dataUrl.split(",")[1];
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        resolve({ mimeType: "image/jpeg", base64, dataUrl, width: w, height: h });
      } catch (err) {
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        reject(err);
      }
    };

    img.onerror = () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      reject(new Error("Không thể đọc được file ảnh để phân tích."));
    };

    if (source instanceof Blob) {
      objectUrl = URL.createObjectURL(source);
      img.src = objectUrl;
    } else if (typeof source === "string") {
      img.src = source;
    } else {
      reject(new Error("Định dạng nguồn ảnh không hợp lệ."));
    }
  });
}

function parseJsonLoose(rawText) {
  if (!rawText) throw new Error("AI trả về nội dung rỗng.");
  let cleaned = rawText.trim();
  if (cleaned.startsWith("```")) {
    cleaned = cleaned.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
  }
  const firstBrace = cleaned.indexOf("{");
  const lastBrace = cleaned.lastIndexOf("}");
  if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
    cleaned = cleaned.slice(firstBrace, lastBrace + 1);
  }
  return JSON.parse(cleaned);
}

async function callGeminiVision({ apiKey, model, preparedImages, extraHint }) {
  const cleanModel = (model || "gemini-2.5-flash").trim();
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(cleanModel)}:generateContent?key=${encodeURIComponent(apiKey.trim())}`;

  const parts = [
    {
      text:
        VISION_SYSTEM_PROMPT +
        `\n\nTổng số ảnh gửi kèm: ${preparedImages.length} (đánh chỉ số image_index từ 0 đến ${preparedImages.length - 1} theo đúng thứ tự).` +
        (extraHint ? `\nThông tin gợi ý bổ sung từ người dùng: ${extraHint}` : ""),
    },
  ];

  preparedImages.forEach((img, idx) => {
    parts.push({ text: `\n--- Ảnh image_index = ${idx} (${img.name || "photo_" + idx}) ---` });
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
    throw new Error(`Lỗi Gemini API (${resp.status}): ${errDetail}`);
  }

  const result = await resp.json();
  const text = result?.candidates?.[0]?.content?.parts?.map((p) => p.text || "").join("") || "";
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
  return parseJsonLoose(text);
}

/**
 * Main entry point to analyze an array of image items: [{ name, fileOrUrl }]
 */
window.VisionAI = {
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

    if (onProgress) {
      const pName = provider === "openai" ? `OpenAI (${model || "gpt-4o"})` : `Google Gemini (${model || "gemini-2.5-flash"})`;
      onProgress(`Đang gửi ${preparedImages.length} ảnh tới ${pName} để đọc chữ viết tay & chuẩn hóa...`);
    }

    if (provider === "openai") {
      return await callOpenAIVision({ apiKey, model, baseUrl, preparedImages, extraHint });
    }
    return await callGeminiVision({ apiKey, model, preparedImages, extraHint });
  },
};
