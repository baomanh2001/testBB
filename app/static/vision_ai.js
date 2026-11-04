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

const VISION_SYSTEM_PROMPT = `Bạn là người hỗ trợ nhập liệu biên bản thí nghiệm điện bằng tiếng Việt. Hãy đọc kỹ từng ảnh gốc, kể cả dấu tiếng Việt, chữ hoa/thường, đơn vị và các chữ số viết tay.

QUY TẮC AN TOÀN:
- Chỉ chép những gì thực sự nhìn thấy. Không đoán, không suy diễn, không sao chép số liệu, tên, ngày, kết luận hay thông tin thiết bị từ mẫu. Ô không có, bị che hoặc không đọc chắc chắn phải để chuỗi rỗng; mô tả cụ thể ảnh, trường và chỗ chưa rõ trong ai_notes để người dùng đối chiếu.
- Giữ đúng tên riêng, dấu tiếng Việt, viết hoa/thường, mã máy, số tem, đơn vị và dấu so sánh như trên ảnh. Không tự động đổi đơn vị hoặc mở rộng chữ viết tắt nếu chưa chắc chắn. Khi có chữ gạch sửa, chỉ chép nội dung sửa nếu đọc rõ và ghi chú.
- Số đo phải chép đúng từng hàng, từng cột và từng pha; phân biệt dấu phẩy thập phân, dấu chấm, dấu lớn hơn và chữ số dễ nhầm. Không tự kết luận đạt hay tự tính giá trị còn thiếu.
- Gộp các trang thuộc cùng một biên bản; source_image_indices chứa chỉ số tất cả các trang tương ứng. Ảnh nhãn hoặc công tơ không phải biên bản đưa vào context_photos, không tự suy đoán tên công trình.
- Phân biệt máy biến áp 1 pha và 3 pha, MCCB và ACB, FCO và LBFCO. Nếu không chắc loại, nêu rõ trong ai_notes; không tạo báo cáo nếu ảnh không phải biên bản.
- Dữ liệu từng ảnh được đánh số từ 0. Không chép các ví dụ hay số mặc định. Duy trì số hàng theo tài liệu, không tự tạo thêm hàng.
- MBA 3 pha: ghép đúng đối tượng đo với R60, R15 và Kht trên cùng một dòng; các cột AB, BC, CA và K1, K2, K3 phải giữ đúng nấc. Các giá trị an, bn, cn là cuộn hạ áp. Ghép bảng tiếp diễn qua các trang, không bỏ sót hoặc lặp nấc.
- ACB/MCCB: giữ đúng các cột điện trở cách điện Close/Open, tiếp xúc pha A/B/C, điện áp thử, đóng cắt, kết quả, số tem. LA/FCO/LBFCO: giữ đúng từng thiết bị và từng cột đo. Cáp ngầm: tách bảng cách điện và bảng điện áp một chiều tăng cao.
- Tủ tụ bù: phân biệt MCCB tổng, MCCB nhánh, Contactor và tụ bù. Chép đủ từng dòng từng bảng; nếu dung lượng được gộp ô dọc, gán dung lượng đó cho từng dòng trong nhóm chỉ khi nhìn rõ phạm vi ô gộp.
- Nếu dữ liệu viết tay khác nội dung in sẵn hoặc khác trang khác, không tự chọn theo một khuôn mẫu; ghi rõ mâu thuẫn và vị trí trong ai_notes.

Trả về duy nhất một đối tượng JSON: {"context_photos":[{"image_index":0,"summary":""}], "reports":[{"report_type":"mba_1p","source_image_indices":[0],"ai_notes":[],"common":{"loai_tieu_de":"","ten_cong_trinh":"","dia_chi":"","chi_danh":"","don_vi_yeu_cau":"","ly_do":"","noi_kiem_dinh":"","ngay_kiem_dinh":""},"data":{}}]}. Các phần tử ví dụ chỉ mô tả cấu trúc, không phải dữ liệu để chép. Chọn đúng report_type trong: mba_1p, mba_3p, mccb, acb, la, fco, lbfco, dtnd, cap_ngam, tu_bu.

Các khóa data cho mỗi loại (chỉ là cấu trúc, giá trị rỗng, không phải dữ liệu mẫu):
{
  "mba_1p": {
    "so_tem": "",
    "hieu_may": "",
    "so_may": "",
    "nuoc_san_xuat": "",
    "nam_san_xuat": "",
    "cong_suat_dinh_muc": "",
    "so_pha": "",
    "tan_so": "",
    "dien_ap_dinh_muc": "",
    "to_dau_day": "",
    "kiem_tra_ben_ngoai": "",
    "cach_dien_rows": [
      {
        "doi_tuong_do": "",
        "r60": "",
        "r15": "",
        "kht": ""
      }
    ],
    "dien_tro_cao_ap": [
      ""
    ],
    "dien_tro_ha_1": "",
    "dien_tro_ha_2": "",
    "ti_so_ha_1": [
      ""
    ],
    "ti_so_ha_2": [
      ""
    ],
    "khong_tai_u0": "",
    "khong_tai_i0": "",
    "khong_tai_i0_pct": "",
    "khong_tai_p0": "",
    "ngan_mach_un": "",
    "ngan_mach_un_pct": "",
    "ngan_mach_in": "",
    "ngan_mach_pn75": "",
    "dien_ap_tang_cao_rows": [
      {
        "doi_tuong_thu": "",
        "u_thu": "",
        "thoi_gian": ""
      }
    ],
    "thiet_bi_kiem_dinh": "",
    "ket_luan": ""
  },
  "mba_3p": {
    "so_tem": "",
    "hieu_may": "",
    "so_may": "",
    "nuoc_san_xuat": "",
    "nam_san_xuat": "",
    "cong_suat_dinh_muc": "",
    "so_pha": "",
    "tan_so": "",
    "dien_ap_dinh_muc": "",
    "to_dau_day": "",
    "kiem_tra_ben_ngoai": "",
    "nhiet_do": "",
    "cach_dien_rows": [
      {
        "doi_tuong_do": "",
        "r60": "",
        "r15": "",
        "kht": ""
      }
    ],
    "dc_cao_ap_rows": [
      {
        "nac": "",
        "ab": "",
        "bc": "",
        "ca": ""
      }
    ],
    "dc_ha_an": "",
    "dc_ha_bn": "",
    "dc_ha_cn": "",
    "ti_so_rows": [
      {
        "nac": "",
        "k1": "",
        "k2": "",
        "k3": ""
      }
    ],
    "khong_tai_u0": "",
    "khong_tai_i0": "",
    "khong_tai_i0_pct": "",
    "khong_tai_p0": "",
    "ngan_mach_un": "",
    "ngan_mach_un_pct": "",
    "ngan_mach_in": "",
    "ngan_mach_pn75": "",
    "dien_ap_tang_cao_rows": [
      {
        "doi_tuong_thu": "",
        "u_thu": "",
        "thoi_gian": ""
      }
    ],
    "thiet_bi_kiem_dinh": "",
    "ket_luan": ""
  },
  "mccb": {
    "hieu": "",
    "so_cuc": "",
    "loai": "",
    "kieu": "",
    "dien_ap_dinh_muc": "",
    "dong_dien_dinh_muc": "",
    "dong_ngan_mach": "",
    "tan_so": "",
    "dien_ap_cach_dien": "",
    "dien_ap_xung": "",
    "kiem_tra_ben_ngoai": "",
    "so_luong": "",
    "rows": [
      {
        "stt": "",
        "rcd_close": "",
        "rcd_open": "",
        "rtx_a": "",
        "rtx_b": "",
        "rtx_c": "",
        "utest": "",
        "dong_cat": "",
        "ket_qua": "",
        "so_tem": ""
      }
    ],
    "thiet_bi_kiem_dinh": "",
    "tieu_chuan_kiem_dinh": "",
    "ket_luan": ""
  },
  "acb": {
    "hieu": "",
    "so_cuc": "",
    "loai": "",
    "kieu": "",
    "dien_ap_dinh_muc": "",
    "dong_dien_dinh_muc": "",
    "dong_ngan_mach": "",
    "tan_so": "",
    "dien_ap_cach_dien": "",
    "dien_ap_xung": "",
    "kiem_tra_ben_ngoai": "",
    "so_luong": "",
    "rows": [
      {
        "stt": "",
        "rcd_close": "",
        "rcd_open": "",
        "rtx_a": "",
        "rtx_b": "",
        "rtx_c": "",
        "utest": "",
        "dong_cat": "",
        "ket_qua": "",
        "so_tem": ""
      }
    ],
    "thiet_bi_kiem_dinh": "",
    "tieu_chuan_kiem_dinh": "",
    "ket_luan": ""
  },
  "la": {
    "vat_lieu_cach_dien": "",
    "mcov": "",
    "dien_ap_dinh_muc": "",
    "tan_so": "",
    "dong_dien_xa": "",
    "kiem_tra_ben_ngoai": "",
    "so_luong": "",
    "rows": [
      {
        "doi_tuong_do": "",
        "dien_tro_cach_dien": "",
        "dong_dien_ro": "",
        "dien_ap_ac": ""
      }
    ],
    "tieu_chuan_kiem_dinh": "",
    "thiet_bi_kiem_dinh": "",
    "ket_luan": ""
  },
  "fco": {
    "vat_lieu_cach_dien": "",
    "dong_dien_dinh_muc": "",
    "dien_ap_dinh_muc": "",
    "kha_nang_cat_ngan_mach": "",
    "kiem_tra_ben_ngoai": "",
    "so_luong": "",
    "rows": [
      {
        "thiet_bi": "",
        "rcd_truoc": "",
        "rcd_sau": "",
        "ac_kho": "",
        "ac_uot": "",
        "dong_cat": "",
        "ket_qua": ""
      }
    ],
    "tieu_chuan_kiem_dinh": "",
    "thiet_bi_kiem_dinh": "",
    "ket_luan": ""
  },
  "lbfco": {
    "vat_lieu_cach_dien": "",
    "dong_dien_dinh_muc": "",
    "dien_ap_dinh_muc": "",
    "kha_nang_cat_ngan_mach": "",
    "kiem_tra_ben_ngoai": "",
    "so_luong": "",
    "rows": [
      {
        "thiet_bi": "",
        "rcd_truoc": "",
        "rcd_sau": "",
        "ac_kho": "",
        "ac_uot": "",
        "dong_cat": "",
        "ket_qua": ""
      }
    ],
    "tieu_chuan_kiem_dinh": "",
    "thiet_bi_kiem_dinh": "",
    "ket_luan": ""
  },
  "dtnd": {
    "rows": [
      {
        "stt": "",
        "chi_danh": "",
        "ket_noi_trung_tinh": "",
        "loai_tiep_dat": "",
        "gia_tri_do": ""
      }
    ],
    "thiet_bi_thu_nghiem": "",
    "ghi_chu_1": "",
    "ghi_chu_2": ""
  },
  "cap_ngam": {
    "so_tem": "",
    "doan_cap_tu": "",
    "doan_cap_den": "",
    "loai_cap": "",
    "tiet_dien": "",
    "dien_ap_dinh_muc": "",
    "tan_so": "",
    "kiem_tra_ben_ngoai": "",
    "nhiet_do": "",
    "cach_dien_rows": [
      {
        "doi_tuong_do": "",
        "tieu_chuan": "",
        "so_lieu_do": ""
      }
    ],
    "dc_tang_cao_rows": [
      {
        "doi_tuong_do": "",
        "thoi_gian": "",
        "dien_ap_thu": "",
        "dong_ro": ""
      }
    ],
    "thiet_bi_kiem_dinh": "",
    "ket_luan": ""
  },
  "tu_bu": {
    "kiem_tra_ben_ngoai": "",
    "mccb_tong_thong_so": "",
    "mccb_tong_so_luong": "",
    "mccb_tong_rows": [
      {
        "stt": "",
        "rcd_close": "",
        "rcd_open": "",
        "rtx_a": "",
        "rtx_b": "",
        "rtx_c": "",
        "utest": "",
        "dong_cat": "",
        "ket_qua": ""
      }
    ],
    "mccb_nhanh_thong_so": "",
    "mccb_nhanh_so_luong": "",
    "mccb_nhanh_rows": [
      {
        "stt": "",
        "rcd_close": "",
        "rcd_open": "",
        "rtx_a": "",
        "rtx_b": "",
        "rtx_c": "",
        "utest": "",
        "dong_cat": "",
        "ket_qua": ""
      }
    ],
    "contactor_thong_so": "",
    "contactor_so_luong": "",
    "contactor_rows": [
      {
        "stt": "",
        "rcd_close": "",
        "rcd_open": "",
        "rtx_a": "",
        "rtx_b": "",
        "rtx_c": "",
        "utest": "",
        "dong_cat": "",
        "ket_qua": ""
      }
    ],
    "tu_bu_so_luong": "",
    "tu_bu_rows": [
      {
        "stt": "",
        "dung_luong": "",
        "r_cach_dien": "",
        "dien_dung": "",
        "ket_qua": ""
      }
    ],
    "thiet_bi_kiem_dinh": "",
    "tieu_chuan_kiem_dinh": "",
    "ket_luan": ""
  }
}
`;

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

async function prepareImageForVision(source, maxEdge = 3000, quality = 0.92) {
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
