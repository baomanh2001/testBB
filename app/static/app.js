/**
 * Main Frontend Application for Toàn Cầu Electrical Testing Report Generator
 * Uses relative /api/... endpoints for full compatibility with Arena Live Preview & local deployments.
 */

(function () {
  "use strict";

  const TYPE_LABELS = {
    tu_bu: "Tủ tụ bù",
    cap_ngam: "Cáp ngầm",
    lbfco: "LBFCO",
    acb: "ACB",
    mba_3p: "MBA 3P",
    mba_1p: "MBA 1P",
    mccb: "MCCB",
    la: "LA",
    fco: "FCO",
    dtnd: "Điện trở nối đất",
  };

  const TYPE_FULL_NAMES = {
    tu_bu: "TỦ TỤ BÙ HẠ THẾ",
    cap_ngam: "THÔNG TUYẾN CÁP NGẦM TRUNG THẾ",
    lbfco: "CẦU CHÌ TỰ RƠI CÓ DẬP HỒ QUANG",
    acb: "MÁY CẮT HẠ THẾ (ACB)",
    mba_3p: "MÁY BIẾN ÁP 3 PHA",
    mba_1p: "MÁY BIẾN ÁP 1 PHA",
    mccb: "MÁY CẮT HẠ THẾ (MCCB)",
    la: "CHỐNG SÉT VAN (LA)",
    fco: "CẦU CHÌ TỰ RƠI (FCO)",
    dtnd: "ĐIỆN TRỞ NỐI ĐẤT",
  };

  const TYPE_SORT_ORDER = { mba_3p: 1, mba_1p: 1, acb: 2, mccb: 2, la: 3, lbfco: 4, fco: 4, dtnd: 5, cap_ngam: 6, tu_bu: 7 };

  const MODEL_OPTIONS = {
    gemini: [
      ...["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.1-pro-preview", "gemini-flash-latest", "gemini-pro-latest"].map(value => ({value, label: value})),
      {value: "__custom__", label: "Model tùy chỉnh…"},
    ],
    openai: [
      { value: "gpt-4o", label: "gpt-4o (Đọc chữ viết tay rất tốt)" },
      { value: "gpt-4.1", label: "gpt-4.1 (Chuẩn xác cao)" },
      { value: "gpt-4o-mini", label: "gpt-4o-mini (Tiết kiệm)" },
    ],
  };

  // Application State
  const state = {
    reports: [],
    activeReportId: null,
    activeImageIndex: 0,
    rightMode: "edit", // 'edit' | 'preview'
    pendingUploads: [], // [{ id, name, file, previewUrl }]
    viewer: { zoom: 1, rotation: 0, panX: 0, panY: 0, isDragging: false, startX: 0, startY: 0 },
    batchConfig: {
      sttStart: 44,
      monthYear: "1126",
      ngayKiemDinh: "01/11/2026",
      ngayPhatHanh: "04/11/2026",
      tenCongTrinh: "Trạm biến áp 50kVA – DOANH NGHIỆP TƯ NHÂN E-GREEN",
      diaChi: "Khu phố Gia Huỳnh, Phường Trảng Bàng, Tỉnh Tây Ninh, Việt Nam",
      donViYeuCau: "DOANH NGHIỆP TƯ NHÂN E-GREEN",
      lyDo: "Sau sự cố",
      noiKiemDinh: "Tại hiện trường",
      nguoiThu: "Nguyễn Trung Nghĩa",
      kiemTra: "Nguyễn Minh Quân",
      phoGiamDoc: "Nguyễn Nhật Tân",
      includeSignature: true,
      customSignatureDataUrl: null,
    },
    aiConfig: loadAiConfig(),
  };

  function loadAiConfig() {
    try {
      const saved = JSON.parse(localStorage.getItem("toancau_ai_config") || "{}");
      return {
        provider: saved.provider || "gemini",
        model: (saved.provider || "gemini") === "gemini" ? window.VisionAI.normalizeGeminiModel(saved.model) : (saved.model || "gpt-4o"),
        apiKey: saved.apiKey || "",
        baseUrl: saved.baseUrl || "https://api.openai.com/v1",
        extraHint: saved.extraHint || "",
      };
    } catch (_) {
      return {
        provider: "gemini",
        model: "gemini-3.8-flash",
        apiKey: "",
        baseUrl: "https://api.openai.com/v1",
        extraHint: "",
      };
    }
  }

  function saveAiConfig() {
    localStorage.setItem("toancau_ai_config", JSON.stringify(state.aiConfig));
    updateAiStatusBadge();
  }

  function esc(val) {
    return String(val ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function uid() {
    return "rep-" + Math.random().toString(36).slice(2, 9) + "-" + Date.now().toString(36);
  }

  function showToast(msg, type = "info") {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.className = `toast no-print ${type}`;
    clearTimeout(showToast._timer);
    showToast._timer = setTimeout(() => el.classList.add("hidden"), 3600);
  }

  function getActiveReport() {
    return state.reports.find((r) => r.id === state.activeReportId) || null;
  }

  const NEW_TYPE_DEFAULTS = {"mba_3p": {"so_tem": "", "hieu_may": "", "so_may": "", "nuoc_san_xuat": "", "nam_san_xuat": "", "cong_suat_dinh_muc": "", "so_pha": "", "tan_so": "", "dien_ap_dinh_muc": "", "to_dau_day": "", "kiem_tra_ben_ngoai": "", "nhiet_do": "", "cach_dien_rows": [{"doi_tuong_do": "", "r60": "", "r15": "", "kht": ""}, {"doi_tuong_do": "", "r60": "", "r15": "", "kht": ""}, {"doi_tuong_do": "", "r60": "", "r15": "", "kht": ""}], "dc_cao_ap_rows": [{"nac": "", "ab": "", "bc": "", "ca": ""}, {"nac": "", "ab": "", "bc": "", "ca": ""}, {"nac": "", "ab": "", "bc": "", "ca": ""}, {"nac": "", "ab": "", "bc": "", "ca": ""}, {"nac": "", "ab": "", "bc": "", "ca": ""}], "dc_ha_an": "", "dc_ha_bn": "", "dc_ha_cn": "", "ti_so_rows": [{"nac": "", "k1": "", "k2": "", "k3": ""}, {"nac": "", "k1": "", "k2": "", "k3": ""}, {"nac": "", "k1": "", "k2": "", "k3": ""}, {"nac": "", "k1": "", "k2": "", "k3": ""}, {"nac": "", "k1": "", "k2": "", "k3": ""}], "khong_tai_u0": "", "khong_tai_i0": "", "khong_tai_i0_pct": "", "khong_tai_p0": "", "ngan_mach_un": "", "ngan_mach_un_pct": "", "ngan_mach_in": "", "ngan_mach_pn75": "", "dien_ap_tang_cao_rows": [{"doi_tuong_thu": "", "u_thu": "", "thoi_gian": ""}, {"doi_tuong_thu": "", "u_thu": "", "thoi_gian": ""}], "thiet_bi_kiem_dinh": "", "ket_luan": ""}, "acb": {"hieu": "", "so_cuc": "", "loai": "", "kieu": "", "dien_ap_dinh_muc": "", "dong_dien_dinh_muc": "", "dong_ngan_mach": "", "tan_so": "", "dien_ap_cach_dien": "", "dien_ap_xung": "", "kiem_tra_ben_ngoai": "", "so_luong": "", "rows": [{"stt": "", "rcd_close": "", "rcd_open": "", "rtx_a": "", "rtx_b": "", "rtx_c": "", "utest": "", "dong_cat": "", "ket_qua": "", "so_tem": ""}], "thiet_bi_kiem_dinh": "", "tieu_chuan_kiem_dinh": "", "ket_luan": ""}, "lbfco": {"vat_lieu_cach_dien": "", "dong_dien_dinh_muc": "", "dien_ap_dinh_muc": "", "kha_nang_cat_ngan_mach": "", "kiem_tra_ben_ngoai": "", "so_luong": "", "rows": [{"thiet_bi": "", "rcd_truoc": "", "rcd_sau": "", "ac_kho": "", "ac_uot": "", "dong_cat": "", "ket_qua": ""}, {"thiet_bi": "", "rcd_truoc": "", "rcd_sau": "", "ac_kho": "", "ac_uot": "", "dong_cat": "", "ket_qua": ""}, {"thiet_bi": "", "rcd_truoc": "", "rcd_sau": "", "ac_kho": "", "ac_uot": "", "dong_cat": "", "ket_qua": ""}], "tieu_chuan_kiem_dinh": "", "thiet_bi_kiem_dinh": "", "ket_luan": ""}, "cap_ngam": {"so_tem": "", "doan_cap_tu": "", "doan_cap_den": "", "loai_cap": "", "tiet_dien": "", "dien_ap_dinh_muc": "", "tan_so": "", "kiem_tra_ben_ngoai": "", "nhiet_do": "", "cach_dien_rows": [{"doi_tuong_do": "", "tieu_chuan": "", "so_lieu_do": ""}, {"doi_tuong_do": "", "tieu_chuan": "", "so_lieu_do": ""}, {"doi_tuong_do": "", "tieu_chuan": "", "so_lieu_do": ""}], "dc_tang_cao_rows": [{"doi_tuong_do": "", "thoi_gian": "", "dien_ap_thu": "", "dong_ro": ""}, {"doi_tuong_do": "", "thoi_gian": "", "dien_ap_thu": "", "dong_ro": ""}, {"doi_tuong_do": "", "thoi_gian": "", "dien_ap_thu": "", "dong_ro": ""}], "thiet_bi_kiem_dinh": "", "ket_luan": ""}, "tu_bu": {"kiem_tra_ben_ngoai": "", "mccb_tong_thong_so": "", "mccb_tong_so_luong": "", "mccb_tong_rows": [{"stt": "", "rcd_close": "", "rcd_open": "", "rtx_a": "", "rtx_b": "", "rtx_c": "", "utest": "", "dong_cat": "", "ket_qua": ""}], "mccb_nhanh_thong_so": "", "mccb_nhanh_so_luong": "", "mccb_nhanh_rows": [{"stt": "", "rcd_close": "", "rcd_open": "", "rtx_a": "", "rtx_b": "", "rtx_c": "", "utest": "", "dong_cat": "", "ket_qua": ""}, {"stt": "", "rcd_close": "", "rcd_open": "", "rtx_a": "", "rtx_b": "", "rtx_c": "", "utest": "", "dong_cat": "", "ket_qua": ""}, {"stt": "", "rcd_close": "", "rcd_open": "", "rtx_a": "", "rtx_b": "", "rtx_c": "", "utest": "", "dong_cat": "", "ket_qua": ""}, {"stt": "", "rcd_close": "", "rcd_open": "", "rtx_a": "", "rtx_b": "", "rtx_c": "", "utest": "", "dong_cat": "", "ket_qua": ""}, {"stt": "", "rcd_close": "", "rcd_open": "", "rtx_a": "", "rtx_b": "", "rtx_c": "", "utest": "", "dong_cat": "", "ket_qua": ""}, {"stt": "", "rcd_close": "", "rcd_open": "", "rtx_a": "", "rtx_b": "", "rtx_c": "", "utest": "", "dong_cat": "", "ket_qua": ""}], "contactor_thong_so": "", "contactor_so_luong": "", "contactor_rows": [{"stt": "", "rcd_close": "", "rcd_open": "", "rtx_a": "", "rtx_b": "", "rtx_c": "", "utest": "", "dong_cat": "", "ket_qua": ""}, {"stt": "", "rcd_close": "", "rcd_open": "", "rtx_a": "", "rtx_b": "", "rtx_c": "", "utest": "", "dong_cat": "", "ket_qua": ""}, {"stt": "", "rcd_close": "", "rcd_open": "", "rtx_a": "", "rtx_b": "", "rtx_c": "", "utest": "", "dong_cat": "", "ket_qua": ""}, {"stt": "", "rcd_close": "", "rcd_open": "", "rtx_a": "", "rtx_b": "", "rtx_c": "", "utest": "", "dong_cat": "", "ket_qua": ""}, {"stt": "", "rcd_close": "", "rcd_open": "", "rtx_a": "", "rtx_b": "", "rtx_c": "", "utest": "", "dong_cat": "", "ket_qua": ""}, {"stt": "", "rcd_close": "", "rcd_open": "", "rtx_a": "", "rtx_b": "", "rtx_c": "", "utest": "", "dong_cat": "", "ket_qua": ""}], "tu_bu_so_luong": "", "tu_bu_rows": [{"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}, {"stt": "", "dung_luong": "", "r_cach_dien": "", "dien_dung": "", "ket_qua": ""}], "thiet_bi_kiem_dinh": "", "tieu_chuan_kiem_dinh": "", "ket_luan": ""}};
  function defaultDataForType(type) {
    if (NEW_TYPE_DEFAULTS[type]) return structuredClone(NEW_TYPE_DEFAULTS[type]);
    if (type === "mba_1p") {
      return {
        so_tem: "",
        hieu_may: "EMC",
        so_may: "",
        nuoc_san_xuat: "Việt Nam",
        nam_san_xuat: "",
        cong_suat_dinh_muc: "50kVA",
        so_pha: "1",
        tan_so: "50Hz",
        dien_ap_dinh_muc: "12,7/0,23 (kV)",
        to_dau_day: "I/I0",
        kiem_tra_ben_ngoai: "Bình thường",
        cach_dien_rows: [
          { doi_tuong_do: "(Cao+Vỏ) –Hạ 1", r60: "", r15: "", kht: "" },
          { doi_tuong_do: "(Cao+vỏ) –Hạ 2", r60: "", r15: "", kht: "" },
          { doi_tuong_do: "Hạ 1 – Hạ 2", r60: "", r15: "", kht: "" },
        ],
        dien_tro_cao_ap: ["", "", "", "", ""],
        dien_tro_ha_1: "",
        dien_tro_ha_2: "",
        ti_so_ha_1: ["", "", "", "", ""],
        ti_so_ha_2: ["", "", "", "", ""],
        khong_tai_u0: "230",
        khong_tai_i0: "",
        khong_tai_i0_pct: "",
        khong_tai_p0: "",
        ngan_mach_un: "",
        ngan_mach_un_pct: "",
        ngan_mach_in: "",
        ngan_mach_pn75: "",
        dien_ap_tang_cao_rows: [
          { doi_tuong_thu: "Cuộn dây cao áp", u_thu: "50", thoi_gian: "1 phút" },
          { doi_tuong_thu: "Cuộn dây hạ áp", u_thu: "3", thoi_gian: "1 phút" },
        ],
        thiet_bi_kiem_dinh: "Kyoritsu 3125A, C.A 6255, DTR 8510, HVTS-70/50, Multimeter, Variac.",
        ket_luan: "Máy biến áp 1 pha trên đạt yêu cầu đóng điện vận hành.",
      };
    }
    if (type === "mccb") {
      return {
        hieu: "MITSUBISHI",
        so_cuc: "03",
        loai: "MCCB",
        kieu: "NF-250",
        dien_ap_dinh_muc: "-",
        dong_dien_dinh_muc: "250A",
        dong_ngan_mach: "-",
        tan_so: "50Hz",
        dien_ap_cach_dien: "-",
        dien_ap_xung: "-",
        kiem_tra_ben_ngoai: "Bình thường",
        so_luong: "01",
        rows: [
          {
            stt: "1",
            rcd_close: ">5000",
            rcd_open: ">5000",
            rtx_a: "",
            rtx_b: "",
            rtx_c: "",
            utest: "3",
            dong_cat: "5",
            ket_qua: "Đạt",
            so_tem: "",
          },
        ],
        thiet_bi_kiem_dinh: "Kyoritsu 3165; Kyoritsu 3125A; CA 6255; CA 6292; HVT-70/50",
        tieu_chuan_kiem_dinh: "QCVN QTĐ-5: 2009/BCT; QT/TNMCĐ",
        ket_luan: "01 máy cắt hạ thế (MCCB) trên đạt yêu cầu đóng điện vận hành.",
      };
    }
    if (type === "la") {
      return {
        vat_lieu_cach_dien: "Polymer",
        mcov: "15,3kV",
        dien_ap_dinh_muc: "18kV",
        tan_so: "50Hz",
        dong_dien_xa: "10 kA",
        kiem_tra_ben_ngoai: "Bình thường",
        so_luong: "01",
        rows: [{ doi_tuong_do: "LA 01", dien_tro_cach_dien: ">10000", dong_dien_ro: "", dien_ap_ac: "35" }],
        tieu_chuan_kiem_dinh: "QCVN QTĐ-5,6,7: 2009/BCT",
        thiet_bi_kiem_dinh: "Kyoritsu 3125A ; HVT-70/50",
        ket_luan: "Một (01) chống sét van trên đạt yêu cầu đóng điện vận hành",
      };
    }
    if (type === "fco") {
      return {
        vat_lieu_cach_dien: "Sứ",
        dong_dien_dinh_muc: "100A",
        dien_ap_dinh_muc: "27kV",
        kha_nang_cat_ngan_mach: "12kA",
        kiem_tra_ben_ngoai: "Bình thường",
        so_luong: "01",
        rows: [
          {
            thiet_bi: "FCO 01",
            rcd_truoc: ">10000",
            rcd_sau: ">10000",
            ac_kho: "60",
            ac_uot: "50",
            dong_cat: "5",
            ket_qua: "Đạt",
          },
        ],
        tieu_chuan_kiem_dinh: "QCVN QTĐ-5,6,7: 2009/BCT",
        thiet_bi_kiem_dinh: "Kyoritsu 3125A; I/IOM 100",
        ket_luan: "Một (01) FCO trên đạt yêu cầu đóng điện vận hành",
      };
    }
    return {
      rows: [
        {
          stt: "1",
          chi_danh: "Điện trở nối đất trạm biến áp",
          ket_noi_trung_tinh: "Có",
          loai_tiep_dat: "Làm việc",
          gia_tri_do: "",
        },
      ],
      thiet_bi_thu_nghiem: "KEW 4105DL",
      ghi_chu_1: "Chỉ danh, vị trí cọc nối đất do đơn vị yêu cầu thử nghiệm cung cấp",
      ghi_chu_2: "Các kết quả đo chỉ có giá trị đối với điểm đo",
    };
  }

  function buildSuggestedFilename(stt, type, data) {
    const prefix = String(stt).padStart(2, "0");
    if (type === "mba_1p") {
      const cs = String(data?.cong_suat_dinh_muc || "50KVA").replace(/\s+/g, "").toUpperCase();
      return `${prefix} BB MBA 1P ${cs}.docx`;
    }
    if (type === "mccb") {
      const dm = String(data?.dong_dien_dinh_muc || "250A").replace(/\s+/g, "").toUpperCase();
      return `${prefix} MCCB ${dm}.docx`;
    }
    if (["mba_3p", "acb", "lbfco", "cap_ngam", "tu_bu"].includes(type)) return `${prefix} BB ${TYPE_LABELS[type]}.docx`;
    if (type === "la") return `${prefix} BB LA.docx`;
    if (type === "fco") return `${prefix} BB FCO.docx`;
    return `${prefix} BB điện trở nối đất.docx`;
  }

  function buildSoBienBan(stt, monthYear) {
    const sttStr = String(stt).padStart(3, "0");
    const my = (monthYear || "1126").trim();
    return `5${sttStr}${my}/BB-TC`;
  }

  function extractMonthYearFromDate(ddmmyyyy) {
    const m = String(ddmmyyyy || "").match(/(\d{1,2})\/(\d{2,4})$/);
    if (!m) return "1126";
    const mm = m[1].padStart(2, "0");
    const yy = m[2].slice(-2);
    return `${mm}${yy}`;
  }

  // =========================================================
  // SAMPLE LOADING & BATCH INITIALIZATION
  // =========================================================
  async function loadSampleBatch() {
    try {
      const resp = await fetch(`/api/samples?station=${encodeURIComponent(document.getElementById("selectSampleStation").value)}`);
      if (!resp.ok) throw new Error("Không thể tải bộ dữ liệu mẫu.");
      const payload = await resp.json();
      const cp = payload.common_project || {};
      const sig = payload.signatory || {};

      state.batchConfig = {
        ...state.batchConfig,
        sttStart: cp.stt_bat_dau || 44,
        monthYear: cp.ma_thang_nam || "1126",
        ngayKiemDinh: cp.ngay_kiem_dinh || "01/11/2026",
        ngayPhatHanh: cp.ngay_phat_hanh || "04/11/2026",
        tenCongTrinh: cp.ten_cong_trinh || "",
        diaChi: cp.dia_chi || "",
        donViYeuCau: cp.don_vi_yeu_cau || "",
        lyDo: cp.ly_do || "Sau sự cố",
        noiKiemDinh: cp.noi_kiem_dinh || "Tại hiện trường",
        nguoiThu: sig.nguoi_thu || "Nguyễn Trung Nghĩa",
        kiemTra: sig.kiem_tra || "Nguyễn Minh Quân",
        phoGiamDoc: sig.pho_giam_doc || "Nguyễn Nhật Tân",
        includeSignature: sig.include_signature !== false,
      };

      state.reports = (payload.reports || []).map((r) => ({
        ...r,
        id: r.id || uid(),
        signatory: {
          ...r.signatory,
          custom_signature_data_url: state.batchConfig.customSignatureDataUrl,
        },
      }));

      state.activeReportId = state.reports[0]?.id || null;
      state.activeImageIndex = 0;
      resetViewerTransform();
      renderAll();
      showToast(`Đã nạp ${state.reports.length} biên bản mẫu!`, "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  // =========================================================
  // UPLOAD QUEUE & AI VISION EXECUTION
  // =========================================================
  function addFilesToPending(fileList) {
    const files = Array.from(fileList || []).filter((f) => f.type.startsWith("image/"));
    if (!files.length) return;
    files.forEach((file) => {
      state.pendingUploads.push({
        id: uid(),
        name: file.name,
        file,
        previewUrl: URL.createObjectURL(file),
      });
    });
    renderPendingUploads();
  }

  function renderPendingUploads() {
    const gal = document.getElementById("pendingGallery");
    const countEl = document.getElementById("pendingCount");
    const runBtn = document.getElementById("btnRunAiOnPending");
    countEl.textContent = String(state.pendingUploads.length);
    runBtn.disabled = state.pendingUploads.length === 0;

    if (!state.pendingUploads.length) {
      gal.classList.add("hidden");
      gal.innerHTML = "";
      return;
    }

    gal.classList.remove("hidden");
    gal.innerHTML =
      state.pendingUploads
        .map(
          (item, i) => `
        <div class="pending-thumb">
          <img src="${esc(item.previewUrl)}" alt="${esc(item.name)}" />
          <span>#${i + 1} ${esc(item.name.length > 20 ? item.name.slice(0, 18) + "…" : item.name)}</span>
          <button type="button" data-remove-pending="${esc(item.id)}" title="Bỏ ảnh này">✕</button>
        </div>`
        )
        .join("") +
      `<button type="button" id="btnClearPending" class="btn btn-sm btn-danger-ghost">Xóa hàng đợi</button>`;

    gal.querySelectorAll("[data-remove-pending]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-remove-pending");
        const found = state.pendingUploads.find((x) => x.id === id);
        if (found) URL.revokeObjectURL(found.previewUrl);
        state.pendingUploads = state.pendingUploads.filter((x) => x.id !== id);
        renderPendingUploads();
      });
    });

    const clearBtn = document.getElementById("btnClearPending");
    if (clearBtn) {
      clearBtn.addEventListener("click", () => {
        state.pendingUploads.forEach((x) => URL.revokeObjectURL(x.previewUrl));
        state.pendingUploads = [];
        renderPendingUploads();
      });
    }
  }

  async function runAiOnImageSources(imageItems, replaceExisting = false) {
    if (!state.aiConfig.apiKey || !state.aiConfig.apiKey.trim()) {
      openModal("modalAiConfig");
      showToast("Vui lòng nhập API Key Gemini hoặc OpenAI trước khi chạy đọc ảnh tự động.", "error");
      return;
    }

    const banner = document.getElementById("aiProgressBanner");
    const bannerTxt = document.getElementById("aiProgressText");
    banner.classList.remove("hidden");

    try {
      const result = await window.VisionAI.analyzeBatch({
        provider: state.aiConfig.provider,
        apiKey: state.aiConfig.apiKey,
        model: state.aiConfig.model,
        baseUrl: state.aiConfig.baseUrl,
        extraHint: state.aiConfig.extraHint,
        imageItems,
        onProgress: (msg) => {
          bannerTxt.textContent = msg;
        },
      });

      const aiReports = Array.isArray(result?.reports) ? result.reports : [];
      const contextPhotos = Array.isArray(result?.context_photos) ? result.context_photos : [];

      if (!aiReports.length) {
        throw new Error("AI không tìm thấy tờ biên bản kiểm định nào trong bộ ảnh đã tải lên.");
      }

      // Sort in standard Toàn Cầu sequence: MBA -> MCCB -> LA -> FCO -> ĐTNĐ
      aiReports.sort((a, b) => (TYPE_SORT_ORDER[a.report_type] || 99) - (TYPE_SORT_ORDER[b.report_type] || 99));

      const baseStt = replaceExisting
        ? Number(state.batchConfig.sttStart || 1)
        : state.reports.length > 0
        ? Math.max(...state.reports.map((r) => Number(r.stt_file) || 0)) + 1
        : Number(state.batchConfig.sttStart || 1);

      const contextImgList = contextPhotos
        .filter((cp) => imageItems[cp.image_index])
        .map((cp) => ({
          label: "Ảnh phụ trợ / Nhãn trạm",
          url: imageItems[cp.image_index].displayUrl,
          note: cp.summary || "",
        }));

      const builtReports = aiReports.map((ar, idx) => {
        const rType = TYPE_LABELS[ar.report_type] ? ar.report_type : "mccb";
        const stt = baseStt + idx;
        const mergedData = { ...defaultDataForType(rType), ...(ar.data || {}) };
        const srcIndices = Array.isArray(ar.source_image_indices) ? ar.source_image_indices : [];
        const imgs = srcIndices
          .filter((i) => imageItems[i])
          .map((i, pageIdx) => ({
            label: srcIndices.length > 1 ? `Trang ${pageIdx + 1}/${srcIndices.length}` : imageItems[i].name || "Ảnh gốc",
            url: imageItems[i].displayUrl,
          }));
        contextImgList.forEach((ci) => imgs.push(ci));

        const commonIn = ar.common || {};
        const ngayPH = state.batchConfig.ngayPhatHanh || "04/11/2026";
        const mmYY = state.batchConfig.monthYear || extractMonthYearFromDate(ngayPH);

        const notes = Array.isArray(ar.ai_notes) ? [...ar.ai_notes] : [];
        contextPhotos.forEach((cp) => {
          if (cp.summary) notes.push(`Thông tin từ ảnh phụ trợ: ${cp.summary}`);
        });

        return {
          id: uid(),
          stt_file: stt,
          report_type: rType,
          filename: buildSuggestedFilename(stt, rType, mergedData),
          images: imgs,
          ai_notes: notes,
          common: {
            so_bien_ban: buildSoBienBan(stt, mmYY),
            ngay_phat_hanh: ngayPH,
            loai_tieu_de:
              rType === "dtnd"
                ? "BIÊN BẢN THỬ NGHIỆM"
                : commonIn.loai_tieu_de || "BIÊN BẢN KIỂM ĐỊNH",
            ten_cong_trinh: commonIn.ten_cong_trinh || state.batchConfig.tenCongTrinh,
            dia_chi: commonIn.dia_chi || state.batchConfig.diaChi,
            chi_danh: commonIn.chi_danh || TYPE_LABELS[rType],
            don_vi_yeu_cau: commonIn.don_vi_yeu_cau || state.batchConfig.donViYeuCau,
            ly_do: commonIn.ly_do || state.batchConfig.lyDo,
            noi_kiem_dinh:
              commonIn.noi_kiem_dinh || (rType === "dtnd" ? "Hiện trường" : "Tại hiện trường"),
            ngay_kiem_dinh: commonIn.ngay_kiem_dinh || state.batchConfig.ngayKiemDinh,
          },
          signatory: {
            nguoi_thu: state.batchConfig.nguoiThu,
            kiem_tra: state.batchConfig.kiemTra,
            pho_giam_doc: state.batchConfig.phoGiamDoc,
            include_signature: state.batchConfig.includeSignature,
            custom_signature_data_url: state.batchConfig.customSignatureDataUrl,
          },
          data: mergedData,
        };
      });

      if (replaceExisting) {
        state.reports = builtReports;
      } else {
        state.reports.push(...builtReports);
      }

      // Sync batchConfig with extracted project info from first report
      if (builtReports[0]?.common?.ten_cong_trinh) {
        state.batchConfig.tenCongTrinh = builtReports[0].common.ten_cong_trinh;
        state.batchConfig.diaChi = builtReports[0].common.dia_chi;
        state.batchConfig.donViYeuCau = builtReports[0].common.don_vi_yeu_cau;
        state.batchConfig.ngayKiemDinh = builtReports[0].common.ngay_kiem_dinh;
      }

      state.activeReportId = builtReports[0].id;
      state.activeImageIndex = 0;
      resetViewerTransform();
      renderAll();
      showToast(`AI đã đọc & tạo thành công ${builtReports.length} biên bản!`, "success");
    } catch (err) {
      showToast(err.message || "Có lỗi khi gọi AI Vision.", "error");
    } finally {
      banner.classList.add("hidden");
    }
  }

  // =========================================================
  // RENDERING ALL UI SECTIONS
  // =========================================================
  function updateAiStatusBadge() {
    const dot = document.getElementById("aiStatusDot");
    const label = document.getElementById("aiStatusLabel");
    if (state.aiConfig.apiKey && state.aiConfig.apiKey.trim()) {
      dot.classList.add("ready");
      const pName = state.aiConfig.provider === "openai" ? "OpenAI" : "Gemini";
      label.textContent = `AI sẵn sàng (${pName})`;
    } else {
      dot.classList.remove("ready");
      label.textContent = "Cấu hình AI Key";
    }
  }

  function renderAll() {
    updateAiStatusBadge();
    const ws = document.getElementById("workspace");
    const emptyWs = document.getElementById("emptyWorkspace");
    const zipBtn = document.getElementById("btnExportZip");
    const zipTxt = document.getElementById("exportZipText");

    zipBtn.disabled = state.reports.length === 0;
    zipTxt.textContent = `Tải trọn bộ ${state.reports.length} file (.zip)`;

    if (state.reports.length === 0) {
      ws.classList.add("hidden");
      emptyWs.classList.remove("hidden");
      document.getElementById("reportTabs").innerHTML = "";
      return;
    }

    ws.classList.remove("hidden");
    emptyWs.classList.add("hidden");

    if (!getActiveReport()) {
      state.activeReportId = state.reports[0].id;
      state.activeImageIndex = 0;
    }

    renderReportTabs();
    renderImageInspector();
    renderRightPane();
  }

  function renderReportTabs() {
    const wrap = document.getElementById("reportTabs");
    wrap.innerHTML =
      state.reports
        .map((r) => {
          const active = r.id === state.activeReportId ? "active" : "";
          const badge = r.stt_file ? `#${r.stt_file}` : "";
          return `
            <button type="button" class="report-tab ${active}" data-tab-id="${esc(r.id)}">
              ${badge ? `<span class="tab-badge">${esc(badge)}</span>` : ""}
              <span>${esc(TYPE_LABELS[r.report_type] || r.report_type)}</span>
            </button>`;
        })
        .join("") +
      (state.reports.length > 0
        ? `<button type="button" id="btnClearBatch" class="btn btn-sm btn-danger-ghost" style="margin-left:6px;" title="Xóa danh sách hiện tại để làm lô trạm mới">Làm lô mới</button>`
        : "");

    wrap.querySelectorAll("[data-tab-id]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.activeReportId = btn.getAttribute("data-tab-id");
        state.activeImageIndex = 0;
        resetViewerTransform();
        renderAll();
      });
    });

    const clearBatchBtn = document.getElementById("btnClearBatch");
    if (clearBatchBtn) {
      clearBatchBtn.addEventListener("click", () => {
        if (confirm("Xóa danh sách biên bản hiện tại để bắt đầu lô trạm mới?")) {
          state.reports = [];
          state.activeReportId = null;
          renderAll();
        }
      });
    }
  }

  // =========================================================
  // LEFT PANE: IMAGE VIEWER
  // =========================================================
  function resetViewerTransform() {
    state.viewer.zoom = 1;
    state.viewer.rotation = 0;
    state.viewer.panX = 0;
    state.viewer.panY = 0;
    applyViewerTransform();
  }

  function applyViewerTransform() {
    const img = document.getElementById("viewerImg");
    const lbl = document.getElementById("zoomLabel");
    if (img) {
      const { panX, panY, zoom, rotation } = state.viewer;
      img.style.transform = `translate(${panX}px, ${panY}px) scale(${zoom}) rotate(${rotation}deg)`;
    }
    if (lbl) {
      lbl.textContent = `${Math.round(state.viewer.zoom * 100)}%`;
    }
  }

  function renderImageInspector() {
    const rep = getActiveReport();
    const tabsEl = document.getElementById("imageTabs");
    const imgEl = document.getElementById("viewerImg");
    const emptyEl = document.getElementById("emptyImageState");

    if (!rep || !rep.images || rep.images.length === 0) {
      tabsEl.innerHTML = `<span style="font-size:12px;color:#94a3b8;">Không có ảnh gốc</span>`;
      imgEl.classList.add("hidden");
      emptyEl.classList.remove("hidden");
      return;
    }

    if (state.activeImageIndex >= rep.images.length) {
      state.activeImageIndex = 0;
    }

    emptyEl.classList.add("hidden");
    imgEl.classList.remove("hidden");
    const activeImg = rep.images[state.activeImageIndex];
    if (imgEl.getAttribute("src") !== activeImg.url) {
      imgEl.setAttribute("src", activeImg.url);
    }
    applyViewerTransform();

    tabsEl.innerHTML = rep.images
      .map(
        (im, i) => `
        <button type="button" class="img-pill ${i === state.activeImageIndex ? "active" : ""}" data-img-idx="${i}">
          ${esc(im.label || `Ảnh ${i + 1}`)}
        </button>`
      )
      .join("");

    tabsEl.querySelectorAll("[data-img-idx]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.activeImageIndex = Number(btn.getAttribute("data-img-idx"));
        resetViewerTransform();
        renderImageInspector();
      });
    });
  }

  // =========================================================
  // RIGHT PANE: FORM EDITOR & LIVE A4 PREVIEW
  // =========================================================
  function renderRightPane() {
    const rep = getActiveReport();
    if (!rep) return;

    const fnInput = document.getElementById("inputFilename");
    fnInput.value = rep.filename || "bien_ban.docx";

    const editBtn = document.getElementById("tabEditMode");
    const prevBtn = document.getElementById("tabPreviewMode");
    const printBtn = document.getElementById("btnPrintPreview");
    const editorEl = document.getElementById("editorContainer");
    const previewEl = document.getElementById("previewContainer");
    const notesBox = document.getElementById("aiNotesBox");

    if (rep.ai_notes && rep.ai_notes.length > 0 && state.rightMode === "edit") {
      notesBox.classList.remove("hidden");
      notesBox.innerHTML = `
        <strong>Ghi chú nhận diện &amp; chuẩn hóa tự động:</strong>
        <ul>${rep.ai_notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>
      `;
    } else {
      notesBox.classList.add("hidden");
    }

    if (state.rightMode === "edit") {
      editBtn.classList.add("active");
      prevBtn.classList.remove("active");
      printBtn.classList.add("hidden");
      editorEl.classList.remove("hidden");
      previewEl.classList.add("hidden");
      renderFormEditor(rep, editorEl);
    } else {
      editBtn.classList.remove("active");
      prevBtn.classList.add("active");
      printBtn.classList.remove("hidden");
      editorEl.classList.add("hidden");
      previewEl.classList.remove("hidden");
      renderA4Preview(rep, previewEl);
    }
  }

  function renderFormEditor(rep, container) {
    const c = rep.common;
    const d = rep.data;
    const sig = rep.signatory;

    let specificHtml = "";

    if (rep.report_type === "mba_1p") {
      const nTaps = (d.dien_tro_cao_ap || []).length || 5;
      specificHtml = `
        <div class="card">
          <div class="card-header">
            <h4 class="card-title">Lý lịch riêng &amp; II. Quy cách kỹ thuật (MBA 1 Pha)</h4>
          </div>
          <div class="form-grid-4">
            <div class="field"><label>Hiệu máy</label><input data-d="hieu_may" value="${esc(d.hieu_may)}" /></div>
            <div class="field"><label>Số máy</label><input data-d="so_may" value="${esc(d.so_may)}" /></div>
            <div class="field"><label>Số tem kiểm định</label><input data-d="so_tem" value="${esc(d.so_tem)}" /></div>
            <div class="field"><label>Năm sản xuất</label><input data-d="nam_san_xuat" value="${esc(d.nam_san_xuat)}" /></div>
          </div>
          <div class="form-grid-4">
            <div class="field"><label>Nước sản xuất</label><input data-d="nuoc_san_xuat" value="${esc(d.nuoc_san_xuat)}" /></div>
            <div class="field"><label>Công suất định mức</label><input data-d="cong_suat_dinh_muc" value="${esc(d.cong_suat_dinh_muc)}" /></div>
            <div class="field"><label>Số pha</label><input data-d="so_pha" value="${esc(d.so_pha)}" /></div>
            <div class="field"><label>Tần số</label><input data-d="tan_so" value="${esc(d.tan_so)}" /></div>
          </div>
          <div class="form-grid-3">
            <div class="field"><label>Điện áp định mức</label><input data-d="dien_ap_dinh_muc" value="${esc(d.dien_ap_dinh_muc)}" /></div>
            <div class="field"><label>Tổ đấu dây</label><input data-d="to_dau_day" value="${esc(d.to_dau_day)}" /></div>
            <div class="field"><label>1. Kiểm tra bên ngoài</label><input data-d="kiem_tra_ben_ngoai" value="${esc(d.kiem_tra_ben_ngoai)}" /></div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h4 class="card-title">III.2. Điện trở cách điện (MΩ)</h4>
            <button type="button" id="btnCalcKht" class="btn btn-sm btn-secondary">Tính tự động Kht = R60 / R15</button>
          </div>
          <div class="data-table-wrap">
            <table class="edit-table">
              <thead><tr><th>Đối tượng đo</th><th>R60’’ (MΩ)</th><th>R15’’ (MΩ)</th><th>Kht</th></tr></thead>
              <tbody>
                ${(d.cach_dien_rows || [])
                  .map(
                    (row, idx) => `
                  <tr>
                    <td><input data-arr="cach_dien_rows" data-idx="${idx}" data-k="doi_tuong_do" value="${esc(row.doi_tuong_do)}" /></td>
                    <td><input data-arr="cach_dien_rows" data-idx="${idx}" data-k="r60" value="${esc(row.r60)}" /></td>
                    <td><input data-arr="cach_dien_rows" data-idx="${idx}" data-k="r15" value="${esc(row.r15)}" /></td>
                    <td><input data-arr="cach_dien_rows" data-idx="${idx}" data-k="kht" value="${esc(row.kht)}" /></td>
                  </tr>`
                  )
                  .join("")}
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h4 class="card-title">III.3 &amp; III.4. Điện trở một chiều cuộn dây &amp; Tỉ số biến áp</h4>
            <div style="display:flex;gap:6px;">
              <button type="button" class="btn btn-sm btn-outline" data-set-taps="3">3 nấc</button>
              <button type="button" class="btn btn-sm btn-outline" data-set-taps="5">5 nấc</button>
            </div>
          </div>
          <label style="font-size:12px;font-weight:700;color:#334155;">3. Điện trở một chiều: Cao áp (Ω) — Hạ áp (mΩ)</label>
          <div class="data-table-wrap">
            <table class="edit-table">
              <thead>
                <tr>
                  ${Array.from({ length: nTaps }, (_, i) => `<th>Cao Nấc ${i + 1} (Ω)</th>`).join("")}
                  <th>HA 1 (mΩ)</th>
                  <th>HA 2 (mΩ)</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  ${Array.from(
                    { length: nTaps },
                    (_, i) => `<td><input data-list="dien_tro_cao_ap" data-idx="${i}" value="${esc(d.dien_tro_cao_ap[i] || "")}" /></td>`
                  ).join("")}
                  <td><input data-d="dien_tro_ha_1" value="${esc(d.dien_tro_ha_1)}" /></td>
                  <td><input data-d="dien_tro_ha_2" value="${esc(d.dien_tro_ha_2)}" /></td>
                </tr>
              </tbody>
            </table>
          </div>

          <label style="font-size:12px;font-weight:700;color:#334155;display:block;margin-top:10px;">4. Tỉ số biến áp: Hạ 1 &amp; Hạ 2</label>
          <div class="data-table-wrap">
            <table class="edit-table">
              <thead>
                <tr>
                  <th>Cuộn</th>
                  ${Array.from({ length: nTaps }, (_, i) => `<th>Nấc ${i + 1}</th>`).join("")}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>Hạ 1</strong></td>
                  ${Array.from(
                    { length: nTaps },
                    (_, i) => `<td><input data-list="ti_so_ha_1" data-idx="${i}" value="${esc((d.ti_so_ha_1 || [])[i] || "")}" /></td>`
                  ).join("")}
                </tr>
                <tr>
                  <td><strong>Hạ 2</strong></td>
                  ${Array.from(
                    { length: nTaps },
                    (_, i) => `<td><input data-list="ti_so_ha_2" data-idx="${i}" value="${esc((d.ti_so_ha_2 || [])[i] || "")}" /></td>`
                  ).join("")}
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h4 class="card-title">III.5, 6, 7. Không tải — Ngắn mạch — Điện áp tăng cao</h4>
          </div>
          <div class="form-grid-4">
            <div class="field"><label>Không tải U0 (V)</label><input data-d="khong_tai_u0" value="${esc(d.khong_tai_u0)}" /></div>
            <div class="field"><label>Không tải I0 (A)</label><input data-d="khong_tai_i0" value="${esc(d.khong_tai_i0)}" /></div>
            <div class="field"><label>Không tải I0 (%)</label><input data-d="khong_tai_i0_pct" value="${esc(d.khong_tai_i0_pct)}" /></div>
            <div class="field"><label>Không tải P0 (W)</label><input data-d="khong_tai_p0" value="${esc(d.khong_tai_p0)}" /></div>
          </div>
          <div class="form-grid-4">
            <div class="field"><label>Ngắn mạch UN (V)</label><input data-d="ngan_mach_un" value="${esc(d.ngan_mach_un)}" /></div>
            <div class="field"><label>Ngắn mạch UN (%)</label><input data-d="ngan_mach_un_pct" value="${esc(d.ngan_mach_un_pct)}" /></div>
            <div class="field"><label>Ngắn mạch IN (A)</label><input data-d="ngan_mach_in" value="${esc(d.ngan_mach_in)}" /></div>
            <div class="field"><label>Ngắn mạch PN75 (W)</label><input data-d="ngan_mach_pn75" value="${esc(d.ngan_mach_pn75)}" /></div>
          </div>
          <div class="data-table-wrap">
            <table class="edit-table">
              <thead><tr><th>Đối tượng thử cao áp</th><th>Uthử (kV)</th><th>Thời gian thử</th></tr></thead>
              <tbody>
                ${(d.dien_ap_tang_cao_rows || [])
                  .map(
                    (row, idx) => `
                  <tr>
                    <td><input data-arr="dien_ap_tang_cao_rows" data-idx="${idx}" data-k="doi_tuong_thu" value="${esc(row.doi_tuong_thu)}" /></td>
                    <td><input data-arr="dien_ap_tang_cao_rows" data-idx="${idx}" data-k="u_thu" value="${esc(row.u_thu)}" /></td>
                    <td><input data-arr="dien_ap_tang_cao_rows" data-idx="${idx}" data-k="thoi_gian" value="${esc(row.thoi_gian)}" /></td>
                  </tr>`
                  )
                  .join("")}
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><h4 class="card-title">IV &amp; V. Thiết bị kiểm định &amp; Kết luận</h4></div>
          <div class="field"><label>Thiết bị kiểm định</label><input data-d="thiet_bi_kiem_dinh" value="${esc(d.thiet_bi_kiem_dinh)}" /></div>
          <div class="field"><label>Kết luận</label><input data-d="ket_luan" value="${esc(d.ket_luan)}" /></div>
        </div>
      `;
    } else if (rep.report_type === "mccb") {
      specificHtml = `
        <div class="card">
          <div class="card-header"><h4 class="card-title">II. Thông số thiết bị (MCCB)</h4></div>
          <div class="form-grid-4">
            <div class="field"><label>Hiệu</label><input data-d="hieu" value="${esc(d.hieu)}" /></div>
            <div class="field"><label>Số cực</label><input data-d="so_cuc" value="${esc(d.so_cuc)}" /></div>
            <div class="field"><label>Loại</label><input data-d="loai" value="${esc(d.loai)}" /></div>
            <div class="field"><label>Kiểu</label><input data-d="kieu" value="${esc(d.kieu)}" /></div>
          </div>
          <div class="form-grid-4">
            <div class="field"><label>Điện áp định mức</label><input data-d="dien_ap_dinh_muc" value="${esc(d.dien_ap_dinh_muc)}" /></div>
            <div class="field"><label>Dòng điện định mức</label><input data-d="dong_dien_dinh_muc" value="${esc(d.dong_dien_dinh_muc)}" /></div>
            <div class="field"><label>Dòng ngắn mạch tối đa</label><input data-d="dong_ngan_mach" value="${esc(d.dong_ngan_mach)}" /></div>
            <div class="field"><label>Tần số</label><input data-d="tan_so" value="${esc(d.tan_so)}" /></div>
          </div>
          <div class="form-grid-4">
            <div class="field"><label>U cách điện định mức</label><input data-d="dien_ap_cach_dien" value="${esc(d.dien_ap_cach_dien)}" /></div>
            <div class="field"><label>U chịu xung định mức</label><input data-d="dien_ap_xung" value="${esc(d.dien_ap_xung)}" /></div>
            <div class="field"><label>Kiểm tra bên ngoài</label><input data-d="kiem_tra_ben_ngoai" value="${esc(d.kiem_tra_ben_ngoai)}" /></div>
            <div class="field"><label>Số lượng</label><input data-d="so_luong" value="${esc(d.so_luong)}" /></div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h4 class="card-title">III. Bảng kết quả thử nghiệm MCCB</h4>
            <button type="button" class="btn btn-sm btn-secondary" data-add-row="mccb">+ Thêm dòng MCCB</button>
          </div>
          <div class="data-table-wrap">
            <table class="edit-table">
              <thead>
                <tr>
                  <th>STT</th><th>Rcđ Close</th><th>Rcđ Open</th><th>Rtx Pha A</th><th>Rtx Pha B</th><th>Rtx Pha C</th>
                  <th>Utest</th><th>Đóng Cắt</th><th>Kết quả</th><th>Số tem</th><th></th>
                </tr>
              </thead>
              <tbody>
                ${(d.rows || [])
                  .map(
                    (r, idx) => `
                  <tr>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="stt" value="${esc(r.stt)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="rcd_close" value="${esc(r.rcd_close)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="rcd_open" value="${esc(r.rcd_open)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="rtx_a" value="${esc(r.rtx_a)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="rtx_b" value="${esc(r.rtx_b)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="rtx_c" value="${esc(r.rtx_c)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="utest" value="${esc(r.utest)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="dong_cat" value="${esc(r.dong_cat)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="ket_qua" value="${esc(r.ket_qua)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="so_tem" value="${esc(r.so_tem)}" /></td>
                    <td><button type="button" class="btn btn-sm btn-danger-ghost" data-del-row="${idx}">✕</button></td>
                  </tr>`
                  )
                  .join("")}
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><h4 class="card-title">IV–VI. Thiết bị, Tiêu chuẩn &amp; Kết luận</h4></div>
          <div class="field"><label>Thiết bị kiểm định</label><input data-d="thiet_bi_kiem_dinh" value="${esc(d.thiet_bi_kiem_dinh)}" /></div>
          <div class="field"><label>Tiêu chuẩn kiểm định</label><input data-d="tieu_chuan_kiem_dinh" value="${esc(d.tieu_chuan_kiem_dinh)}" /></div>
          <div class="field"><label>Kết luận</label><input data-d="ket_luan" value="${esc(d.ket_luan)}" /></div>
        </div>
      `;
    } else if (rep.report_type === "la") {
      specificHtml = `
        <div class="card">
          <div class="card-header"><h4 class="card-title">II. Thông số thiết bị (Chống sét van - LA)</h4></div>
          <div class="form-grid-4">
            <div class="field"><label>Vật liệu cách điện</label><input data-d="vat_lieu_cach_dien" value="${esc(d.vat_lieu_cach_dien)}" /></div>
            <div class="field"><label>MCOV</label><input data-d="mcov" value="${esc(d.mcov)}" /></div>
            <div class="field"><label>Điện áp định mức</label><input data-d="dien_ap_dinh_muc" value="${esc(d.dien_ap_dinh_muc)}" /></div>
            <div class="field"><label>Tần số</label><input data-d="tan_so" value="${esc(d.tan_so)}" /></div>
          </div>
          <div class="form-grid-3">
            <div class="field"><label>Dòng điện xả tối đa</label><input data-d="dong_dien_xa" value="${esc(d.dong_dien_xa)}" /></div>
            <div class="field"><label>Kiểm tra bên ngoài</label><input data-d="kiem_tra_ben_ngoai" value="${esc(d.kiem_tra_ben_ngoai)}" /></div>
            <div class="field"><label>Số lượng</label><input data-d="so_luong" value="${esc(d.so_luong)}" /></div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h4 class="card-title">III. Bảng kết quả kiểm định LA</h4>
            <button type="button" class="btn btn-sm btn-secondary" data-add-row="la">+ Thêm dòng LA</button>
          </div>
          <div class="data-table-wrap">
            <table class="edit-table">
              <thead>
                <tr>
                  <th>Đối tượng đo</th><th>Điện trở cách điện (MΩ)</th><th>Dòng điện rò ở Uđm (µA)</th><th>Điện áp AC tăng cao (kV)</th><th></th>
                </tr>
              </thead>
              <tbody>
                ${(d.rows || [])
                  .map(
                    (r, idx) => `
                  <tr>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="doi_tuong_do" value="${esc(r.doi_tuong_do)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="dien_tro_cach_dien" value="${esc(r.dien_tro_cach_dien)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="dong_dien_ro" value="${esc(r.dong_dien_ro)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="dien_ap_ac" value="${esc(r.dien_ap_ac)}" /></td>
                    <td><button type="button" class="btn btn-sm btn-danger-ghost" data-del-row="${idx}">✕</button></td>
                  </tr>`
                  )
                  .join("")}
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><h4 class="card-title">IV–VI. Tiêu chuẩn, Thiết bị &amp; Kết luận</h4></div>
          <div class="field"><label>Tiêu chuẩn kiểm định</label><input data-d="tieu_chuan_kiem_dinh" value="${esc(d.tieu_chuan_kiem_dinh)}" /></div>
          <div class="field"><label>Thiết bị kiểm định</label><input data-d="thiet_bi_kiem_dinh" value="${esc(d.thiet_bi_kiem_dinh)}" /></div>
          <div class="field"><label>Kết luận</label><input data-d="ket_luan" value="${esc(d.ket_luan)}" /></div>
        </div>
      `;
    } else if (rep.report_type === "fco") {
      specificHtml = `
        <div class="card">
          <div class="card-header"><h4 class="card-title">II. Thông số thiết bị (Cầu chì tự rơi - FCO)</h4></div>
          <div class="form-grid-4">
            <div class="field"><label>Vật liệu cách điện</label><input data-d="vat_lieu_cach_dien" value="${esc(d.vat_lieu_cach_dien)}" /></div>
            <div class="field"><label>Dòng điện định mức</label><input data-d="dong_dien_dinh_muc" value="${esc(d.dong_dien_dinh_muc)}" /></div>
            <div class="field"><label>Điện áp định mức</label><input data-d="dien_ap_dinh_muc" value="${esc(d.dien_ap_dinh_muc)}" /></div>
            <div class="field"><label>Khả năng cắt ngắn mạch</label><input data-d="kha_nang_cat_ngan_mach" value="${esc(d.kha_nang_cat_ngan_mach)}" /></div>
          </div>
          <div class="form-grid-2">
            <div class="field"><label>Kiểm tra bên ngoài</label><input data-d="kiem_tra_ben_ngoai" value="${esc(d.kiem_tra_ben_ngoai)}" /></div>
            <div class="field"><label>Số lượng</label><input data-d="so_luong" value="${esc(d.so_luong)}" /></div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h4 class="card-title">III. Bảng kết quả kiểm định FCO</h4>
            <button type="button" class="btn btn-sm btn-secondary" data-add-row="fco">+ Thêm dòng FCO</button>
          </div>
          <div class="data-table-wrap">
            <table class="edit-table">
              <thead>
                <tr>
                  <th>Thiết bị</th><th>Rcđ Trước CA</th><th>Rcđ Sau CA</th><th>AC Khô (kV)</th><th>AC Ướt (kV)</th><th>Đóng Cắt</th><th>Kết quả</th><th></th>
                </tr>
              </thead>
              <tbody>
                ${(d.rows || [])
                  .map(
                    (r, idx) => `
                  <tr>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="thiet_bi" value="${esc(r.thiet_bi)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="rcd_truoc" value="${esc(r.rcd_truoc)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="rcd_sau" value="${esc(r.rcd_sau)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="ac_kho" value="${esc(r.ac_kho)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="ac_uot" value="${esc(r.ac_uot)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="dong_cat" value="${esc(r.dong_cat)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="ket_qua" value="${esc(r.ket_qua)}" /></td>
                    <td><button type="button" class="btn btn-sm btn-danger-ghost" data-del-row="${idx}">✕</button></td>
                  </tr>`
                  )
                  .join("")}
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><h4 class="card-title">IV–VI. Tiêu chuẩn, Thiết bị &amp; Kết luận</h4></div>
          <div class="field"><label>Tiêu chuẩn kiểm định</label><input data-d="tieu_chuan_kiem_dinh" value="${esc(d.tieu_chuan_kiem_dinh)}" /></div>
          <div class="field"><label>Thiết bị kiểm định</label><input data-d="thiet_bi_kiem_dinh" value="${esc(d.thiet_bi_kiem_dinh)}" /></div>
          <div class="field"><label>Kết luận</label><input data-d="ket_luan" value="${esc(d.ket_luan)}" /></div>
        </div>
      `;
    } else if (rep.report_type === "dtnd") {
      specificHtml = `
        <div class="card">
          <div class="card-header">
            <h4 class="card-title">II. Bảng kết quả thử nghiệm Điện trở nối đất</h4>
            <button type="button" class="btn btn-sm btn-secondary" data-add-row="dtnd">+ Thêm điểm đo</button>
          </div>
          <div class="data-table-wrap">
            <table class="edit-table">
              <thead>
                <tr>
                  <th style="width:52px;">STT</th><th>Chỉ danh điểm đo</th><th>Kết nối trung tính HT</th><th>Loại tiếp đất</th><th>Giá trị đo (Ω)</th><th></th>
                </tr>
              </thead>
              <tbody>
                ${(d.rows || [])
                  .map(
                    (r, idx) => `
                  <tr>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="stt" value="${esc(r.stt)}" /></td>
                    <td><input class="text-left" data-arr="rows" data-idx="${idx}" data-k="chi_danh" value="${esc(r.chi_danh)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="ket_noi_trung_tinh" value="${esc(r.ket_noi_trung_tinh)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="loai_tiep_dat" value="${esc(r.loai_tiep_dat)}" /></td>
                    <td><input data-arr="rows" data-idx="${idx}" data-k="gia_tri_do" value="${esc(r.gia_tri_do)}" /></td>
                    <td><button type="button" class="btn btn-sm btn-danger-ghost" data-del-row="${idx}">✕</button></td>
                  </tr>`
                  )
                  .join("")}
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><h4 class="card-title">III &amp; IV. Thiết bị thử nghiệm &amp; Ghi chú</h4></div>
          <div class="field"><label>Thiết bị thử nghiệm</label><input data-d="thiet_bi_thu_nghiem" value="${esc(d.thiet_bi_thu_nghiem)}" /></div>
          <div class="field"><label>Ghi chú dòng 1</label><input data-d="ghi_chu_1" value="${esc(d.ghi_chu_1)}" /></div>
          <div class="field"><label>Ghi chú dòng 2</label><input data-d="ghi_chu_2" value="${esc(d.ghi_chu_2)}" /></div>
        </div>
      `;
    }

    if (NEW_TYPE_DEFAULTS[rep.report_type]) {
      const label = k => esc(k.replace(/_/g, " "));
      specificHtml = Object.entries(d).map(([key, value]) => {
        if (!Array.isArray(value)) return `<div class="field"><label>${label(key)}</label><input data-d="${esc(key)}" value="${esc(value)}"></div>`;
        const template = (NEW_TYPE_DEFAULTS[rep.report_type][key] || [])[0] || {};
        const cols = Object.keys(value[0] || template);
        return `<div class="card"><h4>${label(key)}</h4><div style="overflow:auto"><table><thead><tr>${cols.map(k => `<th>${label(k)}</th>`).join("")}<th></th></tr></thead><tbody>${value.map((row,i) => `<tr>${cols.map(k => `<td><input data-arr="${esc(key)}" data-idx="${i}" data-k="${esc(k)}" value="${esc(row[k])}"></td>`).join("")}<td><button type="button" data-generic-delete="${esc(key)}" data-idx="${i}">Xóa</button></td></tr>`).join("")}</tbody></table></div><button type="button" data-generic-add="${esc(key)}">+ Thêm dòng</button></div>`;
      }).join("");
    }

    container.innerHTML = `
      <div class="card">
        <div class="card-header">
          <h4 class="card-title">Mẫu biên bản &amp; Số hiệu hồ sơ</h4>
          <select id="selectReportType" style="padding:4px 8px;border-radius:5px;border:1px solid #cbd5e1;font-weight:600;">
            ${Object.entries(TYPE_FULL_NAMES)
              .map(([k, v]) => `<option value="${k}" ${rep.report_type === k ? "selected" : ""}>${esc(v)}</option>`)
              .join("")}
          </select>
        </div>
        <div class="form-grid-3">
          <div class="field"><label>Số biên bản (Góc phải trên)</label><input data-c="so_bien_ban" value="${esc(c.so_bien_ban)}" /></div>
          <div class="field"><label>Ngày phát hành BB</label><input data-c="ngay_phat_hanh" value="${esc(c.ngay_phat_hanh)}" /></div>
          <div class="field"><label>Tiêu đề chính</label><input data-c="loai_tieu_de" value="${esc(c.loai_tieu_de)}" /></div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h4 class="card-title">I. Thông tin công trình</h4>
          <button type="button" id="btnCopyProjectToAll" class="btn btn-sm btn-secondary" title="Copy Tên công trình, Địa chỉ, Đơn vị yêu cầu, Ngày KĐ sang tất cả biên bản trong lô">
            Đồng bộ công trình này cho cả lô
          </button>
        </div>
        <div class="form-grid-2">
          <div class="field"><label>Tên công trình</label><input data-c="ten_cong_trinh" value="${esc(c.ten_cong_trinh)}" /></div>
          <div class="field"><label>Đơn vị yêu cầu</label><input data-c="don_vi_yeu_cau" value="${esc(c.don_vi_yeu_cau)}" /></div>
        </div>
        <div class="field"><label>Địa chỉ</label><input data-c="dia_chi" value="${esc(c.dia_chi)}" /></div>
        <div class="form-grid-4">
          <div class="field"><label>Chỉ danh</label><input data-c="chi_danh" value="${esc(c.chi_danh)}" /></div>
          <div class="field"><label>Lý do kiểm định</label><input data-c="ly_do" value="${esc(c.ly_do)}" /></div>
          <div class="field"><label>Nơi kiểm định</label><input data-c="noi_kiem_dinh" value="${esc(c.noi_kiem_dinh)}" /></div>
          <div class="field"><label>Ngày kiểm định</label><input data-c="ngay_kiem_dinh" value="${esc(c.ngay_kiem_dinh)}" /></div>
        </div>
      </div>

      ${specificHtml}

      <div class="card">
        <div class="card-header">
          <h4 class="card-title">Chữ ký cuối biên bản</h4>
          <label class="checkbox-label" style="font-size:12px;">
            <input type="checkbox" id="chkIncludeSig" ${sig.include_signature !== false ? "checked" : ""} />
            <span>Nhúng ảnh chữ ký Người thử</span>
          </label>
        </div>
        <div class="form-grid-3">
          <div class="field"><label>Người thử</label><input data-s="nguoi_thu" value="${esc(sig.nguoi_thu)}" /></div>
          <div class="field"><label>Kiểm tra</label><input data-s="kiem_tra" value="${esc(sig.kiem_tra)}" /></div>
          <div class="field"><label>P. Giám đốc</label><input data-s="pho_giam_doc" value="${esc(sig.pho_giam_doc)}" /></div>
        </div>
      </div>
    `;

    bindEditorListeners(rep, container);
  }

  function bindEditorListeners(rep, container) {
    container.querySelectorAll("[data-generic-add]").forEach(btn => btn.addEventListener("click", () => {
      const key = btn.dataset.genericAdd;
      const example = rep.data[key][0] || NEW_TYPE_DEFAULTS[rep.report_type][key][0] || {};
      rep.data[key].push(Object.fromEntries(Object.keys(example).map(k => [k, ""])));
      renderFormEditor(rep, container);
    }));
    container.querySelectorAll("[data-generic-delete]").forEach(btn => btn.addEventListener("click", () => {
      rep.data[btn.dataset.genericDelete].splice(Number(btn.dataset.idx), 1);
      renderFormEditor(rep, container);
    }));
    // Switch report type
    const typeSel = container.querySelector("#selectReportType");
    if (typeSel) {
      typeSel.addEventListener("change", () => {
        const nextType = typeSel.value;
        rep.report_type = nextType;
        rep.data = { ...defaultDataForType(nextType), ...rep.data };
        rep.common.loai_tieu_de = nextType === "dtnd" ? "BIÊN BẢN THỬ NGHIỆM" : "BIÊN BẢN KIỂM ĐỊNH";
        if (rep.stt_file) rep.filename = buildSuggestedFilename(rep.stt_file, nextType, rep.data);
        renderAll();
      });
    }

    // Common inputs
    container.querySelectorAll("[data-c]").forEach((inp) => {
      inp.addEventListener("input", () => {
        rep.common[inp.getAttribute("data-c")] = inp.value;
      });
    });

    // Data scalar inputs
    container.querySelectorAll("[data-d]").forEach((inp) => {
      inp.addEventListener("input", () => {
        rep.data[inp.getAttribute("data-d")] = inp.value;
      });
    });

    // Signatory inputs
    container.querySelectorAll("[data-s]").forEach((inp) => {
      inp.addEventListener("input", () => {
        rep.signatory[inp.getAttribute("data-s")] = inp.value;
      });
    });

    const chkSig = container.querySelector("#chkIncludeSig");
    if (chkSig) {
      chkSig.addEventListener("change", () => {
        rep.signatory.include_signature = chkSig.checked;
      });
    }

    // Array-of-objects table inputs
    container.querySelectorAll("[data-arr]").forEach((inp) => {
      inp.addEventListener("input", () => {
        const arrKey = inp.getAttribute("data-arr");
        const idx = Number(inp.getAttribute("data-idx"));
        const k = inp.getAttribute("data-k");
        if (rep.data[arrKey] && rep.data[arrKey][idx]) {
          rep.data[arrKey][idx][k] = inp.value;
        }
      });
    });

    // Simple string list inputs (e.g., dien_tro_cao_ap, ti_so_ha_1)
    container.querySelectorAll("[data-list]").forEach((inp) => {
      inp.addEventListener("input", () => {
        const listKey = inp.getAttribute("data-list");
        const idx = Number(inp.getAttribute("data-idx"));
        if (!Array.isArray(rep.data[listKey])) rep.data[listKey] = [];
        rep.data[listKey][idx] = inp.value;
      });
    });

    // Sync project info from current report to entire batch
    const syncBtn = container.querySelector("#btnCopyProjectToAll");
    if (syncBtn) {
      syncBtn.addEventListener("click", () => {
        state.reports.forEach((other) => {
          if (other.id === rep.id) return;
          other.common.ten_cong_trinh = rep.common.ten_cong_trinh;
          other.common.dia_chi = rep.common.dia_chi;
          other.common.don_vi_yeu_cau = rep.common.don_vi_yeu_cau;
          other.common.ly_do = rep.common.ly_do;
          other.common.ngay_kiem_dinh = rep.common.ngay_kiem_dinh;
          other.common.ngay_phat_hanh = rep.common.ngay_phat_hanh;
        });
        showToast("Đã đồng bộ Thông tin công trình sang tất cả biên bản trong lô!", "success");
      });
    }

    // Auto calculate Kht = R60 / R15 on MBA 1P
    const calcKhtBtn = container.querySelector("#btnCalcKht");
    if (calcKhtBtn) {
      calcKhtBtn.addEventListener("click", () => {
        (rep.data.cach_dien_rows || []).forEach((r) => {
          const v60 = parseFloat(String(r.r60 || "").replace(",", "."));
          const v15 = parseFloat(String(r.r15 || "").replace(",", "."));
          if (!isNaN(v60) && !isNaN(v15) && v15 > 0) {
            r.kht = (v60 / v15).toFixed(2).replace(".", ",");
          }
        });
        renderRightPane();
        showToast("Đã tính tự động hệ số hấp thụ Kht = R60 / R15!", "success");
      });
    }

    // Set tap count (3 or 5) on MBA 1P
    container.querySelectorAll("[data-set-taps]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const n = Number(btn.getAttribute("data-set-taps"));
        ["dien_tro_cao_ap", "ti_so_ha_1", "ti_so_ha_2"].forEach((key) => {
          const cur = Array.isArray(rep.data[key]) ? [...rep.data[key]] : [];
          while (cur.length < n) cur.push("");
          rep.data[key] = cur.slice(0, n);
        });
        renderRightPane();
      });
    });

    // Add dynamic row
    const addRowBtn = container.querySelector("[data-add-row]");
    if (addRowBtn) {
      addRowBtn.addEventListener("click", () => {
        const kind = addRowBtn.getAttribute("data-add-row");
        if (!Array.isArray(rep.data.rows)) rep.data.rows = [];
        const nextIdx = rep.data.rows.length + 1;
        const pad2 = String(nextIdx).padStart(2, "0");
        if (kind === "mccb") {
          rep.data.rows.push({
            stt: String(nextIdx),
            rcd_close: ">5000",
            rcd_open: ">5000",
            rtx_a: "",
            rtx_b: "",
            rtx_c: "",
            utest: "3",
            dong_cat: "5",
            ket_qua: "Đạt",
            so_tem: "",
          });
        } else if (kind === "la") {
          rep.data.rows.push({ doi_tuong_do: `LA ${pad2}`, dien_tro_cach_dien: ">10000", dong_dien_ro: "", dien_ap_ac: "35" });
        } else if (kind === "fco") {
          rep.data.rows.push({
            thiet_bi: `FCO ${pad2}`,
            rcd_truoc: ">10000",
            rcd_sau: ">10000",
            ac_kho: "60",
            ac_uot: "50",
            dong_cat: "5",
            ket_qua: "Đạt",
          });
        } else if (kind === "dtnd") {
          rep.data.rows.push({
            stt: String(nextIdx),
            chi_danh: "",
            ket_noi_trung_tinh: "Có",
            loai_tiep_dat: "Làm việc",
            gia_tri_do: "",
          });
        }
        if (rep.data.so_luong !== undefined) {
          rep.data.so_luong = String(rep.data.rows.length).padStart(2, "0");
        }
        renderRightPane();
      });
    }

    // Delete dynamic row
    container.querySelectorAll("[data-del-row]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = Number(btn.getAttribute("data-del-row"));
        if (Array.isArray(rep.data.rows) && rep.data.rows.length > 1) {
          rep.data.rows.splice(idx, 1);
          if (rep.data.so_luong !== undefined) {
            rep.data.so_luong = String(rep.data.rows.length).padStart(2, "0");
          }
          renderRightPane();
        } else {
          showToast("Cần giữ lại ít nhất 1 dòng kết quả.", "info");
        }
      });
    });
  }

  // =========================================================
  // LIVE A4 WORD PREVIEW RENDERER
  // =========================================================
  function renderHeaderTableHtml(c) {
    return `
      <table class="a4-header-tbl">
        <tr>
          <td rowspan="2" class="a4-header-logo"><img src="/static/assets/logo.jpeg" alt="TC" /></td>
          <td class="a4-company-name">CÔNG TY CP THÍ NGHIỆM ĐIỆN TOÀN CẦU</td>
          <td class="a4-doc-meta"><strong>SỐ:</strong> ${esc(c.so_bien_ban)}</td>
        </tr>
        <tr>
          <td class="a4-doc-kind">${esc(c.loai_tieu_de || "BIÊN BẢN KIỂM ĐỊNH")}</td>
          <td class="a4-doc-meta"><strong>NGÀY:</strong> ${esc(c.ngay_phat_hanh)}</td>
        </tr>
      </table>`;
  }

  function renderSigHtml(sig) {
    const sigSrc = sig.custom_signature_data_url || "/static/assets/signature.png";
    return `
      <div class="a4-sig-grid">
        <div>
          <div>Người thử</div>
          <div class="a4-sig-box">
            ${sig.include_signature !== false ? `<img src="${esc(sigSrc)}" alt="Chữ ký" />` : ""}
          </div>
          <div>${esc(sig.nguoi_thu)}</div>
        </div>
        <div>
          <div>Kiểm tra</div>
          <div class="a4-sig-box"></div>
          <div>${esc(sig.kiem_tra)}</div>
        </div>
        <div>
          <div>P. Giám đốc</div>
          <div class="a4-sig-box"></div>
          <div>${esc(sig.pho_giam_doc)}</div>
        </div>
      </div>`;
  }

  function renderFooterHtml(pageText = "") {
    return `
      <div class="a4-footer">
        <span>ĐC: 213/21 TTH07, Phường Tân Thới Hiệp, TP.HCM</span>
        <span>Điện thoại: 0908 206 854</span>
        <span>Website: http://thinghiemdientoancau.com</span>
        ${pageText ? `<div class="a4-page-num">${esc(pageText)}</div>` : ""}
      </div>`;
  }

  function renderA4Preview(rep, container) {
    const c = rep.common;
    const d = rep.data;
    const sig = rep.signatory;

    if (NEW_TYPE_DEFAULTS[rep.report_type]) {
      const content = Object.entries(d).map(([key, value]) => {
        const label = esc(key.replace(/_/g, " "));
        if (!Array.isArray(value)) return `<div class="a4-line">${label}: ${esc(value)}</div>`;
        const cols = Object.keys(value[0] || {});
        return `<div class="a4-sec-heading">${label}</div><table class="a4-table"><tr>${cols.map(k => `<th>${esc(k.replace(/_/g, " "))}</th>`).join("")}</tr>${value.map(row => `<tr>${cols.map(k => `<td>${esc(row[k])}</td>`).join("")}</tr>`).join("")}</table>`;
      }).join("");
      container.innerHTML = `<div class="a4-page"><img src="/static/assets/watermark.jpeg" class="a4-watermark" alt=""><div class="a4-content">${renderHeaderTableHtml(c)}<div class="a4-equip-title">${esc(TYPE_FULL_NAMES[rep.report_type])}</div>${Object.entries(c).map(([k,v]) => `<div class="a4-line">${esc(k.replace(/_/g, " "))}: ${esc(v)}</div>`).join("")}${content}${renderSigHtml(sig)}</div>${renderFooterHtml()}</div>`;
      return;
    }
    if (rep.report_type === "mba_1p") {
      const nTaps = (d.dien_tro_cao_ap || []).length || 5;
      container.innerHTML = `
        <!-- PAGE 1/2 -->
        <div class="a4-page">
          <img src="/static/assets/watermark.jpeg" class="a4-watermark" alt="" />
          <div class="a4-content">
            ${renderHeaderTableHtml(c)}
            <div class="a4-equip-title">MÁY BIẾN ÁP 1 PHA</div>
            <div class="a4-two-col">
              <strong>I. LÝ LỊCH THIẾT BỊ</strong>
              <span>- Số tem: ${esc(d.so_tem)}</span>
            </div>
            <div class="a4-two-col"><span>- Hiệu máy: ${esc(d.hieu_may)}</span><span>- Số máy: ${esc(d.so_may)}</span></div>
            <div class="a4-two-col"><span>- Nước sản xuất: ${esc(d.nuoc_san_xuat)}</span><span>- Năm sản xuất: ${esc(d.nam_san_xuat)}</span></div>
            <div class="a4-line">- Tên công trình: ${esc(c.ten_cong_trinh)}</div>
            <div class="a4-line">- Địa chỉ: ${esc(c.dia_chi)}</div>
            <div class="a4-line">- Đơn vị yêu cầu: ${esc(c.don_vi_yeu_cau)}</div>
            <div class="a4-line">- Lý do kiểm định: ${esc(c.ly_do)}</div>
            <div class="a4-line">- Nơi kiểm định: ${esc(c.noi_kiem_dinh)}</div>
            <div class="a4-line">- Ngày kiểm định: ${esc(c.ngay_kiem_dinh)}</div>

            <div class="a4-sec-heading"><span>II. QUY CÁCH KỸ THUẬT</span></div>
            <div class="a4-three-col">
              <span>- Công suất định mức: ${esc(d.cong_suat_dinh_muc)}</span>
              <span>- Số pha: ${esc(d.so_pha)}</span>
              <span>- Tần số: ${esc(d.tan_so)}</span>
            </div>
            <div class="a4-two-col">
              <span>- Điện áp định mức: ${esc(d.dien_ap_dinh_muc)}</span>
              <span>- Tổ đấu dây: ${esc(d.to_dau_day)}</span>
            </div>

            <div class="a4-sec-heading"><span>III. KẾT QUẢ KIỂM ĐỊNH</span></div>
            <div class="a4-line">1. Kiểm tra bên ngoài: ${esc(d.kiem_tra_ben_ngoai)}</div>
            <div class="a4-line">2. Điện trở cách điện: (MΩ)</div>
            <table class="a4-table">
              <tr><th>Đối tượng đo</th><th>R<sub>60’’</sub> (MΩ)</th><th>R<sub>15’’</sub> (MΩ)</th><th>K<sub>ht</sub></th></tr>
              ${(d.cach_dien_rows || [])
                .map((r) => `<tr><td>${esc(r.doi_tuong_do)}</td><td>${esc(r.r60)}</td><td>${esc(r.r15)}</td><td>${esc(r.kht)}</td></tr>`)
                .join("")}
            </table>

            <div class="a4-line">3. Điện trở một chiều cuộn dây:</div>
            <table class="a4-table">
              <tr><th></th><th colspan="${nTaps}">Cuộn dây cao áp (Ω)</th><th colspan="2">Cuộn dây hạ áp (mΩ)</th></tr>
              <tr><td>Nấc</td>${Array.from({ length: nTaps }, (_, i) => `<td>${i + 1}</td>`).join("")}<td>HA 1</td><td>HA 2</td></tr>
              <tr>
                <td>Kết quả đo</td>
                ${Array.from({ length: nTaps }, (_, i) => `<td>${esc((d.dien_tro_cao_ap || [])[i] || "")}</td>`).join("")}
                <td>${esc(d.dien_tro_ha_1)}</td><td>${esc(d.dien_tro_ha_2)}</td>
              </tr>
            </table>

            <div class="a4-line">4. Tỉ số biến áp:</div>
            <table class="a4-table">
              <tr><th>Cao</th><th colspan="${nTaps}">Hạ 1</th><th colspan="${nTaps}">Hạ 2</th></tr>
              <tr>
                <td>Nấc</td>
                ${Array.from({ length: nTaps }, (_, i) => `<td>${i + 1}</td>`).join("")}
                ${Array.from({ length: nTaps }, (_, i) => `<td>${i + 1}</td>`).join("")}
              </tr>
              <tr>
                <td>Kết quả đo</td>
                ${Array.from({ length: nTaps }, (_, i) => `<td>${esc((d.ti_so_ha_1 || [])[i] || "")}</td>`).join("")}
                ${Array.from({ length: nTaps }, (_, i) => `<td>${esc((d.ti_so_ha_2 || [])[i] || "")}</td>`).join("")}
              </tr>
            </table>

            <div class="a4-line">5. Thí nghiệm không tải:</div>
            <table class="a4-table">
              <tr><th>Đối tượng đo</th><th>U<sub>0</sub>(V)</th><th>I<sub>0</sub> (A)</th><th>I<sub>0</sub>%</th><th>P<sub>0</sub>(W)</th></tr>
              <tr><td>Kết quả đo</td><td>${esc(d.khong_tai_u0)}</td><td>${esc(d.khong_tai_i0)}</td><td>${esc(d.khong_tai_i0_pct)}</td><td>${esc(d.khong_tai_p0)}</td></tr>
            </table>
          </div>
          ${renderFooterHtml("Trang 1/2")}
        </div>

        <!-- PAGE 2/2 -->
        <div class="a4-page">
          <img src="/static/assets/watermark.jpeg" class="a4-watermark" alt="" />
          <div class="a4-content">
            <div class="a4-line">6. Thí nghiệm ngắn mạch:</div>
            <table class="a4-table">
              <tr><th>Đối tượng đo</th><th>U<sub>N</sub> (V)</th><th>U<sub>N</sub> (%)</th><th>I<sub>N</sub></th><th>P<sub>N75</sub> (W)</th></tr>
              <tr><td>Kết quả đo</td><td>${esc(d.ngan_mach_un)}</td><td>${esc(d.ngan_mach_un_pct)}</td><td>${esc(d.ngan_mach_in)}</td><td>${esc(d.ngan_mach_pn75)}</td></tr>
            </table>

            <div class="a4-line">7. Thử điện áp tăng cao:</div>
            <table class="a4-table" style="width:76%;margin:6px auto 12px;">
              <tr><th>Đối tượng thử</th><th>U<sub>thử</sub> (kV)</th><th>Thời gian thử</th></tr>
              ${(d.dien_ap_tang_cao_rows || [])
                .map((r) => `<tr><td>${esc(r.doi_tuong_thu)}</td><td>${esc(r.u_thu)}</td><td>${esc(r.thoi_gian)}</td></tr>`)
                .join("")}
            </table>

            <div class="a4-line" style="margin-top:10px;"><strong>IV. THIẾT BỊ KIỂM ĐỊNH:</strong> ${esc(d.thiet_bi_kiem_dinh)}</div>
            <div class="a4-line" style="margin-top:6px;"><strong>V. KẾT LUẬN: ${esc(d.ket_luan)}</strong></div>
            ${renderSigHtml(sig)}
          </div>
          ${renderFooterHtml("Trang 2/2")}
        </div>
      `;
      return;
    }

    // 1-Page Templates (MCCB, LA, FCO, ĐTNĐ)
    let bodyHtml = "";
    if (rep.report_type === "mccb") {
      bodyHtml = `
        <div class="a4-equip-title">MÁY CẮT HẠ THẾ (MCCB)</div>
        <div class="a4-sec-heading"><span>I. THÔNG TIN CÔNG TRÌNH</span></div>
        <div class="a4-line">- Tên công trình: ${esc(c.ten_cong_trinh)}</div>
        <div class="a4-line">- Địa chỉ: ${esc(c.dia_chi)}</div>
        <div class="a4-line">- Chỉ danh: ${esc(c.chi_danh)}</div>
        <div class="a4-line">- Đơn vị yêu cầu: ${esc(c.don_vi_yeu_cau)}</div>
        <div class="a4-line">- Lý do kiểm định: ${esc(c.ly_do)}</div>
        <div class="a4-line">- Nơi kiểm định: ${esc(c.noi_kiem_dinh)}</div>
        <div class="a4-line">- Ngày kiểm định: ${esc(c.ngay_kiem_dinh)}</div>

        <div class="a4-sec-heading"><span>II. THÔNG SỐ THIẾT BỊ</span></div>
        <div class="a4-two-col"><span>- Hiệu: ${esc(d.hieu)}</span><span>- Số cực: ${esc(d.so_cuc)}</span></div>
        <div class="a4-two-col"><span>- Loại: ${esc(d.loai)}</span><span>- Kiểu: ${esc(d.kieu)}</span></div>
        <div class="a4-two-col"><span>- Điện áp định mức: ${esc(d.dien_ap_dinh_muc)}</span><span>- Dòng điện định mức: ${esc(d.dong_dien_dinh_muc)}</span></div>
        <div class="a4-two-col"><span>- Dòng điện ngắn mạch tối đa: ${esc(d.dong_ngan_mach)}</span><span>- Tần số: ${esc(d.tan_so)}</span></div>
        <div class="a4-two-col"><span>- Điện áp cách điện định mức: ${esc(d.dien_ap_cach_dien)}</span><span>- Điện áp chịu xung định mức: ${esc(d.dien_ap_xung)}</span></div>

        <div class="a4-sec-heading"><span>III. KẾT QUẢ KIỂM ĐỊNH</span></div>
        <div class="a4-two-col"><span>1. Kiểm tra bên ngoài: ${esc(d.kiem_tra_ben_ngoai)}</span><span>- Số lượng: ${esc(d.so_luong)}</span></div>
        <div class="a4-line">2. Kết quả thử nghiệm:</div>
        <table class="a4-table">
          <tr>
            <th rowspan="2">STT</th><th colspan="2">R cách điện (MΩ)</th><th colspan="3">R tiếp xúc (µΩ)</th>
            <th rowspan="2">Utest<br/>(kV/1’)</th><th rowspan="2">Đóng<br/>Cắt</th><th rowspan="2">Kết quả</th><th rowspan="2">Số tem</th>
          </tr>
          <tr><th>Close</th><th>Open</th><th>Pha A</th><th>Pha B</th><th>Pha C</th></tr>
          ${(d.rows || [])
            .map(
              (r) => `
            <tr>
              <td>${esc(r.stt)}</td><td>${esc(r.rcd_close)}</td><td>${esc(r.rcd_open)}</td>
              <td>${esc(r.rtx_a)}</td><td>${esc(r.rtx_b)}</td><td>${esc(r.rtx_c)}</td>
              <td>${esc(r.utest)}</td><td>${esc(r.dong_cat)}</td><td>${esc(r.ket_qua)}</td><td>${esc(r.so_tem)}</td>
            </tr>`
            )
            .join("")}
        </table>
        <div class="a4-line"><strong>IV. THIẾT BỊ KIỂM ĐỊNH:</strong> ${esc(d.thiet_bi_kiem_dinh)}</div>
        <div class="a4-line"><strong>V. TIÊU CHUẨN KIỂM ĐỊNH:</strong> ${esc(d.tieu_chuan_kiem_dinh)}</div>
        <div class="a4-line"><strong>VI. KẾT LUẬN: ${esc(d.ket_luan)}</strong></div>
      `;
    } else if (rep.report_type === "la") {
      bodyHtml = `
        <div class="a4-equip-title">CHỐNG SÉT VAN (LA)</div>
        <div class="a4-sec-heading"><span>I. THÔNG TIN CÔNG TRÌNH</span></div>
        <div class="a4-line">- Tên công trình: ${esc(c.ten_cong_trinh)}</div>
        <div class="a4-line">- Địa chỉ: ${esc(c.dia_chi)}</div>
        <div class="a4-line">- Chỉ danh: ${esc(c.chi_danh)}</div>
        <div class="a4-line">- Đơn vị yêu cầu: ${esc(c.don_vi_yeu_cau)}</div>
        <div class="a4-line">- Lý do kiểm định: ${esc(c.ly_do)}</div>
        <div class="a4-line">- Nơi kiểm định: ${esc(c.noi_kiem_dinh)}</div>
        <div class="a4-line">- Ngày kiểm định: ${esc(c.ngay_kiem_dinh)}</div>

        <div class="a4-sec-heading"><span>II. THÔNG SỐ THIẾT BỊ</span></div>
        <div class="a4-two-col"><span>- Vật liệu cách điện: ${esc(d.vat_lieu_cach_dien)}</span><span>- MCOV: ${esc(d.mcov)}</span></div>
        <div class="a4-two-col"><span>- Điện áp định mức: ${esc(d.dien_ap_dinh_muc)}</span><span>- Tần số: ${esc(d.tan_so)}</span></div>
        <div class="a4-line">- Dòng điện xả tối đa: ${esc(d.dong_dien_xa)}</div>

        <div class="a4-sec-heading"><span>III. KẾT QUẢ KIỂM ĐỊNH</span></div>
        <div class="a4-two-col"><span>1. Kiểm tra bên ngoài: ${esc(d.kiem_tra_ben_ngoai)}</span><span>- Số lượng: ${esc(d.so_luong)}</span></div>
        <div class="a4-line">2. Kết quả kiểm định:</div>
        <table class="a4-table">
          <tr><th>Đối tượng đo</th><th>Điện trở cách điện (MΩ)</th><th>Dòng điện rò ở điện áp định mức(µA)</th><th>Điện áp AC tăng cao (kV)</th></tr>
          ${(d.rows || [])
            .map((r) => `<tr><td>${esc(r.doi_tuong_do)}</td><td>${esc(r.dien_tro_cach_dien)}</td><td>${esc(r.dong_dien_ro)}</td><td>${esc(r.dien_ap_ac)}</td></tr>`)
            .join("")}
        </table>
        <div class="a4-line"><strong>IV. TIÊU CHUẨN KIỂM ĐỊNH:</strong> ${esc(d.tieu_chuan_kiem_dinh)}</div>
        <div class="a4-line"><strong>V. THIẾT BỊ KIỂM ĐỊNH: ${esc(d.thiet_bi_kiem_dinh)}</strong></div>
        <div class="a4-line"><strong>VI. KẾT LUẬN: ${esc(d.ket_luan)}</strong></div>
      `;
    } else if (rep.report_type === "fco") {
      bodyHtml = `
        <div class="a4-equip-title">CẦU CHÌ TỰ RƠI (FCO)</div>
        <div class="a4-sec-heading"><span>I. THÔNG TIN CÔNG TRÌNH</span></div>
        <div class="a4-line">- Tên công trình: ${esc(c.ten_cong_trinh)}</div>
        <div class="a4-line">- Địa chỉ: ${esc(c.dia_chi)}</div>
        <div class="a4-line">- Chỉ danh: ${esc(c.chi_danh)}</div>
        <div class="a4-line">- Đơn vị yêu cầu: ${esc(c.don_vi_yeu_cau)}</div>
        <div class="a4-line">- Lý do kiểm định: ${esc(c.ly_do)}</div>
        <div class="a4-line">- Nơi kiểm định: ${esc(c.noi_kiem_dinh)}</div>
        <div class="a4-line">- Ngày kiểm định: ${esc(c.ngay_kiem_dinh)}</div>

        <div class="a4-sec-heading"><span>II. THÔNG SỐ THIẾT BỊ</span></div>
        <div class="a4-two-col"><span>- Vật liệu cách điện: ${esc(d.vat_lieu_cach_dien)}</span><span>- Dòng điện định mức: ${esc(d.dong_dien_dinh_muc)}</span></div>
        <div class="a4-two-col"><span>- Điện áp định mức: ${esc(d.dien_ap_dinh_muc)}</span><span>- Khả năng cắt ngắn mạch: ${esc(d.kha_nang_cat_ngan_mach)}</span></div>

        <div class="a4-sec-heading"><span>III. KẾT QUẢ KIỂM ĐỊNH</span></div>
        <div class="a4-two-col"><span>1. Kiểm tra bên ngoài: ${esc(d.kiem_tra_ben_ngoai)}</span><span>- Số lượng: ${esc(d.so_luong)}</span></div>
        <div class="a4-line">2. Kết quả kiểm định:</div>
        <table class="a4-table">
          <tr>
            <th rowspan="2">Thiết bị</th><th colspan="2">R cách điện (MΩ)</th>
            <th colspan="2">Điện áp AC tăng cao tần số công nghiệp (kV)</th>
            <th rowspan="2">Đóng<br/>Cắt</th><th rowspan="2">Kết quả</th>
          </tr>
          <tr><th>Trước khi thử cao áp</th><th>Sau khi thử cao áp</th><th>Điều kiện khô</th><th>Điều kiện ướt</th></tr>
          ${(d.rows || [])
            .map(
              (r) => `
            <tr>
              <td>${esc(r.thiet_bi)}</td><td>${esc(r.rcd_truoc)}</td><td>${esc(r.rcd_sau)}</td>
              <td>${esc(r.ac_kho)}</td><td>${esc(r.ac_uot)}</td><td>${esc(r.dong_cat)}</td><td>${esc(r.ket_qua)}</td>
            </tr>`
            )
            .join("")}
        </table>
        <div class="a4-line"><strong>IV. TIÊU CHUẨN KIỂM ĐỊNH:</strong> ${esc(d.tieu_chuan_kiem_dinh)}</div>
        <div class="a4-line"><strong>V. THIẾT BỊ KIỂM ĐỊNH: ${esc(d.thiet_bi_kiem_dinh)}</strong></div>
        <div class="a4-line"><strong>VI. KẾT LUẬN: ${esc(d.ket_luan)}</strong></div>
      `;
    } else {
      bodyHtml = `
        <div class="a4-equip-title">ĐIỆN TRỞ NỐI ĐẤT</div>
        <div class="a4-sec-heading"><span>I. THÔNG TIN CÔNG TRÌNH</span></div>
        <div class="a4-line">- Tên công trình: ${esc(c.ten_cong_trinh)}</div>
        <div class="a4-line">- Địa chỉ: ${esc(c.dia_chi)}</div>
        <div class="a4-line">- Chỉ danh: ${esc(c.chi_danh)}</div>
        <div class="a4-line">- Đơn vị yêu cầu: ${esc(c.don_vi_yeu_cau)}</div>
        <div class="a4-line">- Lý do thử nghiệm: ${esc(c.ly_do)}</div>
        <div class="a4-line">- Nơi thử nghiệm: ${esc(c.noi_kiem_dinh)}</div>
        <div class="a4-line">- Ngày thử nghiệm: ${esc(c.ngay_kiem_dinh)}</div>

        <div class="a4-sec-heading"><span>II. KẾT QUẢ THỬ NGHIỆM</span></div>
        <table class="a4-table">
          <tr><th>STT</th><th>Chỉ danh</th><th>Tình trạng kết nối với trung tính hệ thống</th><th>Loại tiếp đất</th><th>Giá trị đo (Ω)</th></tr>
          ${(d.rows || [])
            .map(
              (r) => `
            <tr>
              <td>${esc(r.stt)}</td><td>${esc(r.chi_danh)}</td><td>${esc(r.ket_noi_trung_tinh)}</td>
              <td>${esc(r.loai_tiep_dat)}</td><td>${esc(r.gia_tri_do)}</td>
            </tr>`
            )
            .join("")}
        </table>
        <div class="a4-line"><strong>III. THIẾT BỊ THỬ NGHIỆM:</strong> ${esc(d.thiet_bi_thu_nghiem)}</div>
        <div class="a4-line"><strong>IV. GHI CHÚ:</strong></div>
        <div class="a4-line">- ${esc(d.ghi_chu_1)}</div>
        <div class="a4-line">- ${esc(d.ghi_chu_2)}</div>
      `;
    }

    container.innerHTML = `
      <div class="a4-page">
        <img src="/static/assets/watermark.jpeg" class="a4-watermark" alt="" />
        <div class="a4-content">
          ${renderHeaderTableHtml(c)}
          ${bodyHtml}
          ${renderSigHtml(sig)}
        </div>
        ${renderFooterHtml()}
      </div>
    `;
  }

  // =========================================================
  // EXPORT .DOCX & .ZIP HANDLERS
  // =========================================================
  function triggerBlobDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }

  function serializeReportForApi(rep) {
    return {
      report_type: rep.report_type,
      filename: rep.filename || "bien_ban.docx",
      common: rep.common,
      signatory: rep.signatory,
      data: rep.data,
    };
  }

  async function downloadCurrentDocx() {
    const rep = getActiveReport();
    if (!rep) return;
    try {
      const btn = document.getElementById("btnExportDocx");
      btn.disabled = true;
      const resp = await fetch("/api/export/docx", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(serializeReportForApi(rep)),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || "Không thể xuất file Word.");
      }
      const blob = await resp.blob();
      let fn = (rep.filename || "bien_ban.docx").trim();
      if (!fn.toLowerCase().endsWith(".docx")) fn += ".docx";
      triggerBlobDownload(blob, fn);
      showToast(`Đã xuất thành công: ${fn}`, "success");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      document.getElementById("btnExportDocx").disabled = false;
    }
  }

  async function downloadBatchZip() {
    if (!state.reports.length) return;
    try {
      const btn = document.getElementById("btnExportZip");
      btn.disabled = true;
      const stationSlug = (state.batchConfig.donViYeuCau || "Toan_Cau")
        .replace(/[^a-zA-Z0-9À-ỹ\s_-]/g, "")
        .trim()
        .replace(/\s+/g, "_")
        .slice(0, 45);
      const zipName = `Ho_so_BB_${stationSlug || "Toan_Cau"}.zip`;

      const resp = await fetch("/api/export/zip", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          zip_filename: zipName,
          reports: state.reports.map(serializeReportForApi),
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || "Lỗi đóng gói file .zip.");
      }
      const blob = await resp.blob();
      triggerBlobDownload(blob, zipName);
      showToast(`Đã tải trọn bộ ${state.reports.length} biên bản (${zipName})!`, "success");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      document.getElementById("btnExportZip").disabled = false;
    }
  }

  // =========================================================
  // MODALS & GLOBAL EVENT LISTENERS
  // =========================================================
  function openModal(id) {
    document.getElementById(id).classList.remove("hidden");
  }

  function closeModal(id) {
    document.getElementById(id).classList.add("hidden");
  }

  function populateAiModal() {
    const provSel = document.getElementById("cfgProvider");
    const modSel = document.getElementById("cfgModel");
    const keyInp = document.getElementById("cfgApiKey");
    const baseWrap = document.getElementById("cfgBaseUrlWrap");
    const baseInp = document.getElementById("cfgBaseUrl");
    const hintInp = document.getElementById("cfgExtraHint");
    const helpTxt = document.getElementById("cfgHelpText");

    provSel.value = state.aiConfig.provider;
    const renderModelList = () => {
      const p = provSel.value;
      const list = MODEL_OPTIONS[p] || MODEL_OPTIONS.gemini;
      modSel.innerHTML = list.map((m) => `<option value="${m.value}">${esc(m.label)}</option>`).join("");
      if (list.some((m) => m.value === state.aiConfig.model)) {
        modSel.value = state.aiConfig.model;
      }
      if (!list.some(m => m.value === state.aiConfig.model) && p === "gemini") {
        modSel.value = "__custom__";
        document.getElementById("cfgCustomModel").value = state.aiConfig.model;
      }
      document.getElementById("cfgCustomModelWrap").classList.toggle("hidden", modSel.value !== "__custom__");
      document.getElementById("btnFetchLiveModels").classList.toggle("hidden", p !== "gemini");
      if (p === "openai") {
        baseWrap.classList.remove("hidden");
        helpTxt.innerHTML = `Sử dụng OpenAI API Key (<code>sk-...</code>). Key chỉ lưu trên trình duyệt của bạn.`;
      } else {
        baseWrap.classList.add("hidden");
        helpTxt.innerHTML = `Lấy mã Gemini miễn phí tại <strong>aistudio.google.com/apikey</strong>. API Key chỉ lưu cục bộ trên trình duyệt của bạn.`;
      }
    };
    modSel.onchange = () => document.getElementById("cfgCustomModelWrap").classList.toggle("hidden", modSel.value !== "__custom__");
    provSel.onchange = renderModelList;
    renderModelList();
    keyInp.value = state.aiConfig.apiKey || "";
    baseInp.value = state.aiConfig.baseUrl || "https://api.openai.com/v1";
    hintInp.value = state.aiConfig.extraHint || "";
  }

  function populateBatchModal() {
    const bc = state.batchConfig;
    const first = state.reports[0];
    if (first) {
      bc.tenCongTrinh = first.common.ten_cong_trinh || bc.tenCongTrinh;
      bc.diaChi = first.common.dia_chi || bc.diaChi;
      bc.donViYeuCau = first.common.don_vi_yeu_cau || bc.donViYeuCau;
      bc.lyDo = first.common.ly_do || bc.lyDo;
      bc.ngayKiemDinh = first.common.ngay_kiem_dinh || bc.ngayKiemDinh;
      bc.ngayPhatHanh = first.common.ngay_phat_hanh || bc.ngayPhatHanh;
    }

    document.getElementById("batchSttStart").value = bc.sttStart;
    document.getElementById("batchMonthYear").value = bc.monthYear;
    document.getElementById("batchNgayKiemDinh").value = bc.ngayKiemDinh;
    document.getElementById("batchNgayPhatHanh").value = bc.ngayPhatHanh;
    document.getElementById("batchTenCongTrinh").value = bc.tenCongTrinh;
    document.getElementById("batchDonViYeuCau").value = bc.donViYeuCau;
    document.getElementById("batchDiaChi").value = bc.diaChi;
    document.getElementById("batchLyDo").value = bc.lyDo;
    document.getElementById("batchNoiKiemDinh").value = bc.noiKiemDinh;
    document.getElementById("batchNguoiThu").value = bc.nguoiThu;
    document.getElementById("batchKiemTra").value = bc.kiemTra;
    document.getElementById("batchPhoGiamDoc").value = bc.phoGiamDoc;
    document.getElementById("batchIncludeSig").checked = bc.includeSignature !== false;
    document.getElementById("batchSigPreview").src =
      bc.customSignatureDataUrl || "/static/assets/signature.png";
  }

  function renumberAllReports() {
    const start = Number(state.batchConfig.sttStart || 1);
    const mmYY = state.batchConfig.monthYear || extractMonthYearFromDate(state.batchConfig.ngayPhatHanh);
    state.reports.forEach((r, idx) => {
      const stt = start + idx;
      r.stt_file = stt;
      r.common.so_bien_ban = buildSoBienBan(stt, mmYY);
      r.filename = buildSuggestedFilename(stt, r.report_type, r.data);
    });
    renderAll();
    showToast("Đã đánh lại Số biên bản & Tên file theo thứ tự!", "success");
  }

  function initEvents() {
    // Load Samples
    document.getElementById("btnLoadSamples").addEventListener("click", loadSampleBatch);
    document.getElementById("btnEmptyLoadSample").addEventListener("click", loadSampleBatch);

    // Export
    document.getElementById("btnExportDocx").addEventListener("click", downloadCurrentDocx);
    document.getElementById("btnExportZip").addEventListener("click", downloadBatchZip);
    document.getElementById("btnPrintPreview").addEventListener("click", () => window.print());

    // Filename edit
    document.getElementById("inputFilename").addEventListener("input", (e) => {
      const rep = getActiveReport();
      if (rep) rep.filename = e.target.value;
    });

    // Delete current report
    document.getElementById("btnDeleteReport").addEventListener("click", () => {
      const rep = getActiveReport();
      if (!rep) return;
      state.reports = state.reports.filter((r) => r.id !== rep.id);
      state.activeReportId = state.reports[0]?.id || null;
      renderAll();
    });

    // Mode switch (Edit vs Preview)
    document.getElementById("tabEditMode").addEventListener("click", () => {
      state.rightMode = "edit";
      renderRightPane();
    });
    document.getElementById("tabPreviewMode").addEventListener("click", () => {
      state.rightMode = "preview";
      renderRightPane();
    });

    // File Upload & Drag-Drop
    const fileInput = document.getElementById("fileInput");
    const dropZone = document.getElementById("dropZone");

    document.getElementById("btnPickFiles").addEventListener("click", () => fileInput.click());
    document.getElementById("btnEmptyUpload").addEventListener("click", () => fileInput.click());
    dropZone.querySelector(".dropzone-content").addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", () => {
      addFilesToPending(fileInput.files);
      fileInput.value = "";
    });

    dropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropZone.classList.add("dragover");
    });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
    dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropZone.classList.remove("dragover");
      if (e.dataTransfer?.files?.length) addFilesToPending(e.dataTransfer.files);
    });

    // Run AI Vision on Pending Uploads
    document.getElementById("btnRunAiOnPending").addEventListener("click", async () => {
      if (!state.pendingUploads.length) return;
      const items = state.pendingUploads.map((u) => ({
        name: u.name,
        source: u.file,
        displayUrl: u.previewUrl,
      }));
      const shouldReplace =
        state.reports.length > 0 &&
        state.reports.every((r) => String(r.id).startsWith("sample-"));
      await runAiOnImageSources(items, shouldReplace);
      state.pendingUploads = [];
      renderPendingUploads();
    });

    // Re-run AI Vision on Current Report's Attached Images
    document.getElementById("btnReocrCurrent").addEventListener("click", async () => {
      const rep = getActiveReport();
      if (!rep || !rep.images || !rep.images.length) {
        showToast("Biên bản này chưa có ảnh đính kèm để đọc AI.", "info");
        return;
      }
      const items = rep.images.map((im, idx) => ({
        name: im.label || `Ảnh ${idx + 1}`,
        source: im.url,
        displayUrl: im.url,
      }));
      await runAiOnImageSources(items, false);
    });

    // Attach extra photo to current report
    const attachInp = document.getElementById("attachPhotoInput");
    document.getElementById("btnAttachPhoto").addEventListener("click", () => attachInp.click());
    document.getElementById("btnAttachPhotoEmpty").addEventListener("click", () => attachInp.click());
    attachInp.addEventListener("change", () => {
      const rep = getActiveReport();
      if (!rep) return;
      const files = Array.from(attachInp.files || []);
      if (!rep.images) rep.images = [];
      files.forEach((f) => {
        rep.images.push({ label: f.name, url: URL.createObjectURL(f) });
      });
      state.activeImageIndex = rep.images.length - 1;
      attachInp.value = "";
      renderImageInspector();
    });

    // Manual Add Report Menu
    const addBtn = document.getElementById("btnAddManual");
    const addMenu = document.getElementById("addManualMenu");
    addBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      addMenu.classList.toggle("hidden");
    });
    document.addEventListener("click", () => addMenu.classList.add("hidden"));
    addMenu.querySelectorAll("[data-type]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const rType = btn.getAttribute("data-type");
        const nextStt =
          state.reports.length > 0
            ? Math.max(...state.reports.map((r) => Number(r.stt_file) || 0)) + 1
            : Number(state.batchConfig.sttStart || 1);
        const d = defaultDataForType(rType);
        const newRep = {
          id: uid(),
          stt_file: nextStt,
          report_type: rType,
          filename: buildSuggestedFilename(nextStt, rType, d),
          images: [],
          ai_notes: [],
          common: {
            so_bien_ban: buildSoBienBan(nextStt, state.batchConfig.monthYear),
            ngay_phat_hanh: state.batchConfig.ngayPhatHanh,
            loai_tieu_de: rType === "dtnd" ? "BIÊN BẢN THỬ NGHIỆM" : "BIÊN BẢN KIỂM ĐỊNH",
            ten_cong_trinh: state.batchConfig.tenCongTrinh,
            dia_chi: state.batchConfig.diaChi,
            chi_danh: TYPE_LABELS[rType],
            don_vi_yeu_cau: state.batchConfig.donViYeuCau,
            ly_do: state.batchConfig.lyDo,
            noi_kiem_dinh: rType === "dtnd" ? "Hiện trường" : state.batchConfig.noiKiemDinh,
            ngay_kiem_dinh: state.batchConfig.ngayKiemDinh,
          },
          signatory: {
            nguoi_thu: state.batchConfig.nguoiThu,
            kiem_tra: state.batchConfig.kiemTra,
            pho_giam_doc: state.batchConfig.phoGiamDoc,
            include_signature: state.batchConfig.includeSignature,
            custom_signature_data_url: state.batchConfig.customSignatureDataUrl,
          },
          data: d,
        };
        state.reports.push(newRep);
        state.activeReportId = newRep.id;
        state.activeImageIndex = 0;
        renderAll();
      });
    });

    document.getElementById("btnRenumberAll").addEventListener("click", renumberAllReports);

    // Image Viewer Zoom / Rotate / Pan
    document.getElementById("btnZoomIn").addEventListener("click", () => {
      state.viewer.zoom = Math.min(4, +(state.viewer.zoom + 0.25).toFixed(2));
      applyViewerTransform();
    });
    document.getElementById("btnZoomOut").addEventListener("click", () => {
      state.viewer.zoom = Math.max(0.25, +(state.viewer.zoom - 0.25).toFixed(2));
      applyViewerTransform();
    });
    document.getElementById("btnZoomReset").addEventListener("click", resetViewerTransform);
    document.getElementById("btnRotateLeft").addEventListener("click", () => {
      state.viewer.rotation -= 90;
      applyViewerTransform();
    });
    document.getElementById("btnRotateRight").addEventListener("click", () => {
      state.viewer.rotation += 90;
      applyViewerTransform();
    });

    const vp = document.getElementById("imageViewport");
    vp.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        const delta = e.deltaY < 0 ? 0.15 : -0.15;
        state.viewer.zoom = Math.min(4.5, Math.max(0.25, +(state.viewer.zoom + delta).toFixed(2)));
        applyViewerTransform();
      },
      { passive: false }
    );
    vp.addEventListener("mousedown", (e) => {
      state.viewer.isDragging = true;
      state.viewer.startX = e.clientX - state.viewer.panX;
      state.viewer.startY = e.clientY - state.viewer.panY;
      vp.classList.add("grabbing");
    });
    window.addEventListener("mousemove", (e) => {
      if (!state.viewer.isDragging) return;
      state.viewer.panX = e.clientX - state.viewer.startX;
      state.viewer.panY = e.clientY - state.viewer.startY;
      applyViewerTransform();
    });
    window.addEventListener("mouseup", () => {
      state.viewer.isDragging = false;
      vp.classList.remove("grabbing");
    });

    // Modals Close Buttons
    document.querySelectorAll("[data-close]").forEach((btn) => {
      btn.addEventListener("click", () => closeModal(btn.getAttribute("data-close")));
    });

    // AI Config Modal
    document.getElementById("btnAiConfig").addEventListener("click", () => {
      populateAiModal();
      openModal("modalAiConfig");
    });
    document.getElementById("btnFetchLiveModels").addEventListener("click", async () => {
      try {
        const models = await window.VisionAI.fetchAvailableGeminiModels(document.getElementById("cfgApiKey").value);
        const sel = document.getElementById("cfgModel");
        for (const m of models) if (![...sel.options].some(o => o.value === m.value)) sel.add(new Option(m.label, m.value));
        showToast(`Đã tải ${models.length} model.`, "success");
      } catch (err) { showToast(err.message, "error"); }
    });
    document.getElementById("btnSaveAiConfig").addEventListener("click", () => {
      state.aiConfig.provider = document.getElementById("cfgProvider").value;
      state.aiConfig.model = document.getElementById("cfgModel").value === "__custom__" ? document.getElementById("cfgCustomModel").value.trim() : document.getElementById("cfgModel").value;
      if (!state.aiConfig.model) { showToast("Vui lòng nhập Model ID.", "error"); return; }
      state.aiConfig.apiKey = document.getElementById("cfgApiKey").value.trim();
      state.aiConfig.baseUrl = document.getElementById("cfgBaseUrl").value.trim() || "https://api.openai.com/v1";
      state.aiConfig.extraHint = document.getElementById("cfgExtraHint").value.trim();
      saveAiConfig();
      closeModal("modalAiConfig");
      showToast("Đã lưu cấu hình AI Vision!", "success");
    });
    document.getElementById("btnClearAiKey").addEventListener("click", () => {
      state.aiConfig.apiKey = "";
      document.getElementById("cfgApiKey").value = "";
      saveAiConfig();
      showToast("Đã xóa API Key khỏi trình duyệt.", "info");
    });

    // Batch Settings Modal
    document.getElementById("btnBatchSettings").addEventListener("click", () => {
      populateBatchModal();
      openModal("modalBatchSettings");
    });

    const sigInp = document.getElementById("batchSigFileInput");
    document.getElementById("btnUploadCustomSig").addEventListener("click", () => sigInp.click());
    sigInp.addEventListener("change", () => {
      const f = sigInp.files?.[0];
      if (!f) return;
      const reader = new FileReader();
      reader.onload = () => {
        state.batchConfig.customSignatureDataUrl = reader.result;
        document.getElementById("batchSigPreview").src = reader.result;
      };
      reader.readAsDataURL(f);
    });
    document.getElementById("btnResetSig").addEventListener("click", () => {
      state.batchConfig.customSignatureDataUrl = null;
      document.getElementById("batchSigPreview").src = "/static/assets/signature.png";
    });

    document.getElementById("btnApplyBatchSync").addEventListener("click", () => {
      const bc = state.batchConfig;
      bc.sttStart = Number(document.getElementById("batchSttStart").value || 1);
      bc.monthYear = document.getElementById("batchMonthYear").value.trim() || "1126";
      bc.ngayKiemDinh = document.getElementById("batchNgayKiemDinh").value.trim();
      bc.ngayPhatHanh = document.getElementById("batchNgayPhatHanh").value.trim();
      bc.tenCongTrinh = document.getElementById("batchTenCongTrinh").value.trim();
      bc.donViYeuCau = document.getElementById("batchDonViYeuCau").value.trim();
      bc.diaChi = document.getElementById("batchDiaChi").value.trim();
      bc.lyDo = document.getElementById("batchLyDo").value.trim();
      bc.noiKiemDinh = document.getElementById("batchNoiKiemDinh").value.trim();
      bc.nguoiThu = document.getElementById("batchNguoiThu").value.trim();
      bc.kiemTra = document.getElementById("batchKiemTra").value.trim();
      bc.phoGiamDoc = document.getElementById("batchPhoGiamDoc").value.trim();
      bc.includeSignature = document.getElementById("batchIncludeSig").checked;

      state.reports.forEach((r, idx) => {
        const stt = bc.sttStart + idx;
        r.stt_file = stt;
        r.common.so_bien_ban = buildSoBienBan(stt, bc.monthYear);
        r.common.ngay_kiem_dinh = bc.ngayKiemDinh;
        r.common.ngay_phat_hanh = bc.ngayPhatHanh;
        r.common.ten_cong_trinh = bc.tenCongTrinh;
        r.common.don_vi_yeu_cau = bc.donViYeuCau;
        r.common.dia_chi = bc.diaChi;
        r.common.ly_do = bc.lyDo;
        r.common.noi_kiem_dinh =
          r.report_type === "dtnd" && bc.noiKiemDinh === "Tại hiện trường"
            ? "Hiện trường"
            : bc.noiKiemDinh;
        r.signatory = {
          nguoi_thu: bc.nguoiThu,
          kiem_tra: bc.kiemTra,
          pho_giam_doc: bc.phoGiamDoc,
          include_signature: bc.includeSignature,
          custom_signature_data_url: bc.customSignatureDataUrl,
        };
        r.filename = buildSuggestedFilename(stt, r.report_type, r.data);
      });

      closeModal("modalBatchSettings");
      renderAll();
      showToast("Đã đồng bộ Thông tin trạm, Người ký & Số BB cho toàn bộ lô!", "success");
    });
  }

  // Boot!
  initEvents();
  loadSampleBatch();
})();
