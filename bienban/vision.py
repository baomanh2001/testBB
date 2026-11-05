"""Nhận dạng ảnh biên bản bằng Gemini → JSON đúng cấu trúc của tool.

Module này **chỉ** lo phần giao tiếp với Google Generative Language API và
phần dựng prompt; việc dựng form chỉnh sửa nằm ở web UI, việc điền Word nằm ở
:mod:`bienban.fill`.

Vì sao gọi qua backend (khác với một số bản tham khảo gọi trực tiếp từ
trình duyệt):

* API key **không bao giờ** gửi xuống trình duyệt (không lộ khi chia sẻ link,
  không lọt vào lịch sử/extension của máy người dùng);
* ảnh được nén (``MAX_EDGE``) và gửi 1 lần cho cả lô → ít request hơn;
* có timeout, thử lại và thông báo lỗi tiếng Việt rõ ràng.

Cấu hình:

* ``GEMINI_API_KEY`` – biến môi trường, ưu tiên cao nhất;
* hoặc header ``X-Gemini-Key`` do người dùng nhập trên web (không lưu ở server).
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import urllib.error
import urllib.request
from typing import Iterable

from .schema import FORM_GROUPS
from .spec import DATA_KEYS, TITLES

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
#: Model mặc định. Để trống = **tự dò** model mới nhất mà key đang dùng được.
#: Google khai tử model liên tục (2.0-flash, 2.5-pro…), nên đừng ghim cứng.
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "")
#: Dùng khi chưa dò được (chưa có key / mất mạng)
SAFE_MODEL = os.environ.get("GEMINI_SAFE_MODEL", "gemini-2.5-flash")
#: Số token tối đa cho mỗi lần gọi — Gemini 3 trừ cả token "thinking" vào đây
MAX_OUTPUT_TOKENS = 32768
TIMEOUT = int(os.environ.get("GEMINI_TIMEOUT", "180"))
#: Cạnh dài tối đa khi gửi ảnh. Ảnh biên bản chụp bằng điện thoại (1920×2560)
#: có 3–5 dòng bảng trong nửa dưới khung; thu về 2000px thì mỗi dòng chữ viết
#: tay chỉ còn ~24px — dưới ngưỡng đọc tin cậy nên AI hay điền nhầm ô. 2600px
#: giữ được nét chữ mà vẫn nhẹ (Gemini tự chia ô 768px, 2600px ≈ 3×3 ô).
MAX_EDGE = int(os.environ.get("GEMINI_MAX_EDGE", "2600"))
JPEG_QUALITY = 92
MAX_IMAGES = 24

# Model cũ đã bị khai tử → tự chuyển sang model mặc định
_RETIRED = re.compile(r"^gemini-(1\.|pro-vision|3\.5-flash|3\.7-)")

FORM_DEVICE = {
    "44": "Máy biến áp 1 pha (MBA 1P)",
    "45": "Máy cắt hạ thế (MCCB)",
    "46": "Chống sét van (LA)",
    "47": "Cầu chì tự rơi (FCO)",
    "48": "Điện trở nối đất",
    "49": "Máy biến áp 3 pha (MBA 3P, Dyn11)",
    "93": "Máy cắt hạ thế (ACB)",
    "97": "Thông tuyến cáp ngầm trung thế",
}


# Các mã lỗi nên thử bước kế tiếp trong chuỗi dự phòng (model/key khác)
_RETRY_STATUS = {429, 500, 502, 503, 504}
#: Thông báo của Google khi model đã bị khai tử (đi kèm HTTP 404)
_GONE = re.compile(r"no longer available|is not found|does not exist|has been (shut ?down|retired)",
                   re.I)


#: Dấu hiệu nhận diện nhanh một tờ biên bản thuộc mẫu nào (dùng trong prompt).
FORM_ANCHORS = {
    "44": "tiêu đề “MÁY BIẾN ÁP 1 PHA”; bảng cách điện có (Cao+Vỏ) – Hạ 1 / – Hạ 2 / Hạ 1 – Hạ 2",
    "45": "tiêu đề “MÁY CẮT HẠ THẾ (MCCB)”; bảng có R cách điện Close/Open + R tiếp xúc Pha A/B/C + Số tem",
    "46": "tiêu đề “CHỐNG SÉT VAN (LA)”; bảng có Điện trở cách điện / Dòng điện rò (µA) / Điện áp AC tăng cao",
    "47": "tiêu đề “CẦU CHÌ TỰ RƠI (FCO)”; bảng có Trước khi thử cao áp / Sau khi thử cao áp",
    "48": "tiêu đề “ĐIỆN TRỞ NỐI ĐẤT”; bảng có Tình trạng kết nối trung tính / Loại tiếp đất / Giá trị đo (Ω)",
    "49": "tiêu đề “MÁY BIẾN ÁP 3 PHA”; Số pha 03 + Tổ đấu dây Dyn11; bảng cách điện Cao – Vỏ / Cao – Hạ / Hạ – Vỏ; tỉ số K1/K2/K3",
    "93": "tiêu đề “MÁY CẮT HẠ THẾ (ACB)”; Giống MCCB nhưng ghi rõ ACB, dòng định mức lớn (800–4000A), có Điện áp cách điện + Điện áp chịu xung",
    "97": "tiêu đề “THÔNG TUYẾN CÁP NGẦM TRUNG THẾ”; có Đoạn cáp đi từ / Đến / Tiết diện và 2 bảng đo THEO PHA (Pha 1–(2+3+vỏ)…)",
}


class GeminiError(RuntimeError):
    """Lỗi khi gọi Gemini (đã dịch sang tiếng Việt cho người dùng cuối)."""


class GeminiBusy(GeminiError):
    """Model đang bận / quá tải / hết hạn mức — nên chuyển sang phương án khác.

    ``status`` là mã HTTP gốc (429, 503…) để chuỗi dự phòng quyết định.
    """

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


class GeminiFatal(GeminiError):
    """Lỗi không thể sửa bằng cách đổi model/key (sai định dạng ảnh, JSON hỏng…)."""


# --------------------------------------------------------------------------- #
# Ảnh
# --------------------------------------------------------------------------- #
def prepare_image(blob: bytes, max_edge: int = MAX_EDGE) -> tuple[str, str]:
    """Thu nhỏ ảnh và trả về ``(mime, base64)``.

    Không có Pillow thì gửi nguyên ảnh gốc – Gemini vẫn đọc được, chỉ tốn băng
    thông hơn.
    """
    try:
        from PIL import Image, ImageOps
    except Exception:                                   # pragma: no cover
        return _guess_mime(blob), base64.b64encode(blob).decode()

    try:
        img = Image.open(io.BytesIO(blob))
        img = ImageOps.exif_transpose(img)               # ảnh chụp dọc bằng điện thoại
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.thumbnail((max_edge, max_edge), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return "image/jpeg", base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return _guess_mime(blob), base64.b64encode(blob).decode()


def _guess_mime(blob: bytes) -> str:
    if blob[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #
#: Mô tả ngắn "ô này nằm ở đâu / viết thế nào trên tờ biên bản" – giúp AI khỏi
#: nhầm giữa các ô gần giống nhau (số máy vs số tem, R60 vs R15, K1 vs K2…).
FIELD_HINTS: dict[str, str] = {
    "so_tem": "ô “- Số tem:” ở góc phải mục I (6 chữ số, thường dán tem vàng)",
    "so_may": "ô “- Số máy:” ngay dưới Số tem",
    "hieu_may": "ô “- Hiệu máy:” dòng đầu mục I; với mẫu 49 khoá này cũng nhận "
                "tên hãng ghi ở tiêu đề thiết bị",
    "hieu": "ô “- Hiệu:” mục II (tên hãng, VD MITSUBISHI)",
    "nam_san_xuat": "ô “- Năm sản xuất:” (4 chữ số)",
    "nuoc_san_xuat": "ô “- Nước sản xuất:” (VD Việt Nam)",
    "cong_suat_dinh_muc": "ô “- Công suất định mức:” mục II, giữ nguyên chữ kVA",
    "so_pha": "ô “- Số pha:” – MBA 1 pha ghi 01, MBA 3 pha ghi 03",
    "tan_so": "ô “- Tần số:” (50 Hz hoặc 50/60Hz)",
    "dien_ap_dinh_muc": "ô “- Điện áp định mức:” – ghi cả cấp áp, VD 22/0.4kV",
    "to_dau_day": "ô “- Tổ đấu dây:” – MBA 3 pha thường Dyn11, 1 pha là I/I0",
    "nhiet_do": "ô “- Nhiệt độ:” cạnh dòng “Điện trở cách điện” (chỉ số °C)",
    "kiem_tra_ben_ngoai": "dòng “1. Kiểm tra bên ngoài:” – thường “Bình thường”",
    "r60": "cột R60″(MΩ) – giá trị lớn hơn R15″",
    "r15": "cột R15″(MΩ) – giá trị nhỏ hơn R60″",
    "knt": "cột Kht – luôn ≈ R60/R15, dùng để kiểm tra chéo",
    "cao_vo": "dòng “Cao – Vỏ”",
    "cao_ha": "dòng “Cao – Hạ”",
    "ha_vo": "dòng “Hạ – Vỏ”",
    "cao_vo_ha1": "dòng “(Cao+Vỏ) – Hạ 1”",
    "cao_vo_ha2": "dòng “(Cao+Vỏ) – Hạ 2”",
    "ha1_ha2": "dòng “Hạ 1 – Hạ 2”",
    "ab": "cột AB của cuộn dây cao áp (mỗi nấc 1 giá trị)",
    "bc": "cột BC của cuộn dây cao áp",
    "ca": "cột CA của cuộn dây cao áp",
    "k1": "cột K1 trong bảng “Tỉ số biến áp” (KHÔNG phải Kht của bảng cách điện)",
    "k2": "cột K2 trong bảng “Tỉ số biến áp”",
    "k3": "cột K3 trong bảng “Tỉ số biến áp”",
    "u0_V": "ô U0(V) của bảng “Thử nghiệm không tải”",
    "i0_A": "ô I0(A) – dòng không tải",
    "i0_pct": "ô I0% – phần trăm dòng không tải",
    "p0_W": "ô P0(W) – tổn thất không tải",
    "uk_V": "ô UN(V) của bảng “Thử nghiệm ngắn mạch”",
    "uk_pct": "ô UN(%) – điện áp ngắn mạch phần trăm",
    "ik_A": "ô IN(A) – dòng ngắn mạch",
    "pk_W": "ô PN75(W) – tổn thất ngắn mạch",
    "thoi_gian": "cột “Thời gian thử” (thường “1 phút”)",
    "gia_tri_do_Ohm": "cột “Giá trị đo (Ω)” của bảng nối đất",
    "chi_danh": "dòng “- Chỉ danh:” – nếu ảnh không ghi thì BỎ TRỐNG",
}


def _field_lines(form: str) -> list[str]:
    """Sinh danh sách khoá + nhãn + **vị trí trên tờ giấy** cho từng ô.

    Mỗi dòng nói rõ khoá JSON, nhãn tiếng Việt, đơn vị, kiểu dữ liệu và ô đó
    nằm ở đâu — nhờ vậy AI ít nhầm giữa các ô gần giống nhau (số máy/số tem,
    R60/R15, K1/Kht…).
    """
    out: list[str] = []
    for g in FORM_GROUPS[form]:
        if "table" in g:
            t = g["table"]
            cols = []
            for c in t["columns"]:
                col = f'"{c["key"]}" ({c["label"]}'
                if c.get("unit"):
                    col += f', {c["unit"]}'
                cols.append(col + ")")
            if t.get("stt"):
                cols.insert(0, '"stt" (số thứ tự)')
            out.append(f'  - "{t["key"]}": danh sách dòng, mỗi dòng là object gồm '
                       + ", ".join(cols))
            if t.get("kind") == "fixed":
                parts = []
                for r in t["rows"]:
                    where = FIELD_HINTS.get(r["key"])
                    parts.append(f'"{r["key"]}" ({r["label"]}'
                                 + (f' – {where}' if where else "") + ")")
                out.append(f"    + object này có {len(t['rows'])} khoá, theo đúng thứ tự in: "
                           + "; ".join(parts))
            continue
        for f in g.get("fields", []):
            unit = f' – đơn vị {f["unit"]}' if f.get("unit") else ""
            # gợi ý vị trí trên tờ giấy (ưu tiên) rồi mới tới hint của schema
            where = FIELD_HINTS.get(f["key"].split(".")[-1]) or FIELD_HINTS.get(f["key"])
            hint = f" – {f['hint']}" if f.get("hint") else ""
            typ = {"code": "chỉ chữ số", "date": "dd/mm/yyyy",
                   "number": "số, dấu phẩy thập phân"}.get(f["type"], "")
            extra = f" [{typ}]" if typ else ""
            loc = f" – ĐỌC Ở: {where}" if where else ""
            out.append(f'  - "{f["key"]}": {f["label"]}{unit}{extra}{loc}{hint}')
    return out


def build_prompt(forms: Iterable[str] | None = None) -> str:
    """Prompt tiếng Việt, liệt kê đúng khoá cần đọc cho từng mẫu."""
    forms = list(forms or sorted(FORM_GROUPS))
    parts: list[str] = []
    parts.append(
        "Bạn là chuyên viên nhập liệu của CÔNG TY CP THÍ NGHIỆM ĐIỆN TOÀN CẦU.\n"
        "Nhiệm vụ: đọc các ảnh biên bản kiểm định viết tay tại hiện trường (mỗi ảnh "
        "là một tờ biên bản, có thể có ảnh thiết bị/tem dán kèm) và trả về DUY NHẤT "
        "một khối JSON để phần mềm tự điền vào biểu mẫu Word.\n"
    )
    parts.append("=== QUY TẮC BẮT BUỘC ===\n"
                 "1. Chỉ đọc những gì NHÌN THẤY trên ảnh. Không suy đoán, không bịa số, "
                 "không tự tính toán thay người ghi (trừ khi ảnh đã ghi sẵn kết quả).\n"
                 "2. Không đọc chắc chắn được thì để chuỗi rỗng \"\" và ghi lý do vào "
                 "\"ai_notes\" của biên bản đó. Tuyệt đối không đoán bừa.\n"
                 "3. Giữ nguyên dấu tiếng Việt, chữ hoa/thường và đơn vị như trên ảnh "
                 "(kV, kVA, A, MΩ, µΩ, Ω, Hz, µA, kW, %). Không đổi đơn vị.\n"
                 "4. Số đo dùng DẤU PHẨY thập phân kiểu Việt Nam: 3,52 (không viết 3.52). "
                 "Giá trị vượt thang đo giữ nguyên dấu lớn hơn: >5000, >10000.\n"
                 "5. Ngày tháng xuất ra đúng dạng dd/mm/yyyy, đủ 2 chữ số ngày và tháng: "
                 "\"1/11/2026\" → \"01/11/2026\".\n"
                 "6. Số máy, số tem, số công tơ: chỉ ghi chữ số (bỏ dấu cách, gạch ngang, "
                 "ký tự lạ). Chữ O/o thành số 0, chữ l/I thành số 1 nếu rõ ràng là chữ số.\n"
                 "7. Một tờ biên bản có thể chụp thành nhiều ảnh (ảnh trên + ảnh dưới): "
                 "hãy GỘP lại thành một biên bản, không tạo 2 biên bản trùng.\n"
                 "8. Chỉ tạo những dòng bảng có thật trên ảnh. Không thêm dòng trống.\n"
                 "9. Trả về JSON thuần, không kèm lời giải thích, không dùng markdown.\n"
                 "10. Phân biệt máy biến áp 1 pha (mẫu 44) và 3 pha (mẫu 49) bằng "
                 "TIÊU ĐỀ và BẢNG, không đoán:\n"
                 "    • Tiêu đề ghi “MÁY BIẾN ÁP 3 PHA”, hoặc mục II có Số pha = 03 / "
                 "Tổ đấu dây kiểu Dyn11, Yyn0 → mẫu 49.\n"
                 "    • Bảng cách điện có dòng “Cao – Vỏ”, “Cao – Hạ”, “Hạ – Vỏ” → mẫu 49.\n"
                 "    • Bảng cách điện có “(Cao+Vỏ) – Hạ 1”, “(Cao+Vỏ) – Hạ 2”, "
                 "“Hạ 1 – Hạ 2” → mẫu 44.\n"
                 "    • Bảng tỉ số có cột K1/K2/K3 → mẫu 49; có cột “Hạ 1” và "
                 "“Hạ 2” → mẫu 44.\n"
                 "    Nếu ảnh là MBA 3 pha thì TUYỆT ĐỐI không trả về report_type 44.\n"
                 "11. Đọc bảng theo đúng hàng/cột in trên giấy, không suy diễn:\n"
                 "    • Mỗi dòng nấc chỉ lấy đúng ô giao với cột đó (AB, BC, CA…).\n"
                 "    • Ô gộp ghi nhiều dòng (an: 0,885 / bn: 0,887 / cn: 0,889) thì "
                 "tách thành từng khoá riêng, không gộp thành một chuỗi.\n"
                 "12. Tự kiểm chéo trước khi trả về, nếu lệch thì đọc lại ảnh:\n"
                 "    • Kht ≈ R60/R15 (sai quá 0,05 → ghi vào ai_notes).\n"
                 "    • R60 > R15 ở mọi dòng cách điện.\n"
                 "    • Dãy nấc phải giảm dần hoặc tăng dần đều, không nhảy cóc.\n"
                 "    • K1, K2, K3 ở cùng một nấc phải xấp xỉ bằng nhau.\n"
                 "13. Số pha và tổ đấu dây phải khớp nhau: 03 ↔ Dyn11/Yyn0…; "
                 "01 ↔ I/I0.\n"
                 "14. ĐỌC THEO Ô, KHÔNG ĐỌC THEO TRÍ NHỚ MẪU:\n"
                 "    • Mỗi mục có thể chụp thành 1 ảnh; ảnh có thể bị nghiêng, "
                 "ngược, thiếu mép. Xoay trong đầu cho thẳng rồi mới đọc.\n"
                 "    • Khi một ảnh chứa nhiều tờ chồng nhau: chỉ đọc TỜ TRÊN CÙNG.\n"
                 "    • Chữ viết tay hay ghi tắt: 'Bthg' = Bình thường, 'Đ' = Đạt, "
                 "'KĐ' = không đạt. Không rõ thì để trống và ghi ai_notes.\n"
                 "    • Ô có sẵn chữ in (nhãn, đơn vị) KHÔNG phải dữ liệu — chỉ lấy "
                 "phần chữ/số người ta VIẾT TAY thêm vào.\n"
                 "    • Tờ nào ghi số hiệu dạng 50xxxxxx/BB-TC thì chép NGUYÊN số đó; "
                 "hai số cuối nhóm giữa là tháng+năm của đợt (VD 50921026 = mẫu 92, "
                 "tháng 10/2026) — dùng để phát hiện ảnh lẫn đợt.\n"
                 "15. Ảnh KHÔNG phải biên bản (chụp tem, công tơ, tủ điện, bao bì, "
                 "mặt bằng) → chỉ ghi vào \"context_photos\", KHÔNG tạo report.\n"
                 "16. Nếu ảnh là tờ của MẪU CHƯA CÓ trong danh sách dưới đây, "
                 "ghi vào \"unknown_forms\": [{\"image_index\": N, "
                 "\"title\": \"tiêu đề đọc được\"}] — đừng gán bừa sang mẫu khác.\n")

    parts.append("=== DANH SÁCH ẢNH ===\n"
                 "Mỗi ảnh được gửi kèm nhãn \"image_index = N\" ngay trước nó. "
                 "Dùng đúng số N đó khi trích dẫn nguồn.\n")

    parts.append("=== KHOÁ CHUNG (mọi biên bản) ===\n"
                 '"thong_tin_chung": {\n'
                 '  "ten_cong_trinh": tên công trình/trạm, ví dụ "Trạm biến áp 50kVA – DOANH NGHIỆP TƯ NHÂN E-GREEN",\n'
                 '  "dia_chi": địa chỉ đầy đủ (khu phố/xã/huyện/tỉnh),\n'
                 '  "don_vi_yêu_cầu": tên đơn vị yêu cầu kiểm định (viết đúng như ảnh),\n'
                 '  "ly_do_kiem_dinh": một trong "Sau sự cố", "Định kỳ", "Lắp đặt mới", "Hiện trường",\n'
                 '  "noi_kiem_dinh": "Tại hiện trường" hoặc "Tại phòng thí nghiệm",\n'
                 '  "ngay_kiem_dinh": dd/mm/yyyy,\n'
                 '  "ngay_lap_bien_ban": dd/mm/yyyy,\n'
                 '  "can_bo_ky_ten": {"nguoi_thu": …, "nguoi_kiem_tra": …, "p_giam_doc": …}\n'
                 "}\n")

    parts.append("=== CẤU TRÚC TRẢ VỀ ===\n"
                 "{\n"
                 '  "context_photos": [{"image_index": 0, "summary": "ảnh này chụp gì"}],\n'
                 '  "unknown_forms": [{"image_index": 0, "title": "tiêu đề tờ chưa có mẫu"}],\n'
                 '  "reports": [\n'
                 "    {\n"
                 '      "report_type": "'
                 + '" | "'.join(forms) + '",\n'
                 '      "source_image_indices": [các image_index của tờ biên bản này],\n'
                 '      "confidence": "high" | "medium" | "low",\n'
                 '      "ai_notes": ["điểm chưa chắc chắn, chữ mờ, số bị sửa…"],\n'
                 '      "thong_tin_chung": {…như trên, chỉ các khoá đọc được…},\n'
                 '      "data": {…các khoá của mẫu tương ứng…}\n'
                 "    }\n"
                 "  ]\n"
                 "}\n"
                 f'Nếu ảnh không phải biên bản nào trong {len(forms)} mẫu dưới đây '
                 'thì cho vào "context_photos" và KHÔNG tạo report.\n')

    for form in forms:
        anchor = FORM_ANCHORS.get(form)
        parts.append(f"=== MẪU {form}: {TITLES[form]} – {FORM_DEVICE[form]} "
                     f"(khoá report_type = \"{form}\") ===\n")
        if anchor:
            parts.append(f"NHẬN DIỆN MẪU {form}: {anchor}\n")
        parts.append("Các khoá của \"data\":\n"
                     + "\n".join(_field_lines(form)) + "\n")
        key = DATA_KEYS[form]
        parts.append(f"(Khi phần mềm lưu, \"data\" của mẫu {form} nằm dưới khoá "
                     f"\"{key}\".)\n")

    parts.append(
        "=== VÍ DỤ MỘT DÒNG BẢNG ===\n"
        'Mẫu 45, dòng thứ nhất: {"stt": "1", "rcd_close": ">5000", "rcd_open": ">5000", '
        '"rtx_a": "273", "rtx_b": "275", "rtx_c": "279", "utest": "3", "dong_cat": "5", '
        '"ket_qua": "Đạt", "so_tem": "017215"}\n'
        "=== VÍ DỤ BẢNG 3 PHA (mẫu 49) ===\n"
        'Cách điện: {"cao_vo": {"r60": "15300", "r15": "11300", "knt": "1,35"}, '
        '"cao_ha": {…}, "ha_vo": {…}}\n'
        'Cuộn cao áp: {"cao_ap": {"ab": ["3,413", …5 nấc], "bc": […], "ca": […]}, '
        '"ha_ap_mOhm": {"an": "0,885", "bn": "0,887", "cn": "0,889"}}\n'
        'Tỉ số: {"k1": ["57,759", …5 nấc], "k2": […], "k3": […]}\n'
        'Điện áp thử: {"cao_vo": "50", "ha_vo": "3", "thoi_gian": "1 phút"}\n'
        "Nhãn \"Chỉ danh\" nếu ảnh không ghi thì BỎ TRỐNG (phần mềm tự ghép).\n"
        "Nhãn \"Kết luận\" chỉ chép khi ảnh có câu kết luận; không có thì bỏ trống.\n"
    )
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Phân loại ảnh trước khi đọc (giải quyết "up nhiều ảnh không biết chia sao")
# --------------------------------------------------------------------------- #
#: Từ khoá trên TIÊU ĐỀ tờ biên bản → mẫu tương ứng. Đọc từ trên xuống, dòng
#: nào khớp trước thì thắng. Xếp theo độ đặc hiệu (ACB trước MCCB, LBFCO
#: trước FCO) để không nhầm các loại na ná nhau.
_TITLE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("93", ("máy cắt hạ thế (acb)", "(acb)", "air circuit breaker")),
    ("45", ("máy cắt hạ thế (mccb)", "(mccb)", "mccb")),
    ("95", ("lbfco", "có dập hồ quang")),
    ("47", ("cầu chì tự rơi", "fco")),
    ("46", ("chống sét van", "(la)")),
    ("94", ("chống sét van", "la ")),
    ("97", ("thông tuyến cáp", "cáp ngầm")),
    ("109", ("tụ bù", "tụ điện")),
    ("49", ("máy biến áp 3 pha", "mba 3 pha", "3 pha")),
    ("44", ("máy biến áp 1 pha", "mba 1 pha", "1 pha")),
    ("48", ("điện trở nối đất", "nối đất")),
]


def _title_of_form(form: str) -> str:
    return TITLES.get(form, "")


def guess_form(text: str, available: Iterable[str] | None = None) -> str:
    """Đoán số mẫu từ **chữ đọc được trên ảnh** (chỉ dùng khi AI trả về lạ).

    Trả về ``""`` nếu không đủ căn cứ — khi đó để người dùng chọn tay.
    """
    hay = (text or "").lower()
    hay = re.sub(r"\s+", " ", hay)
    pool = set(available or TEMPLATES)
    for form, keys in _TITLE_RULES:
        if form not in pool:
            continue
        if any(k in hay for k in keys):
            return form
    # cuối cùng: so khớp đúng tiêu đề in trong biểu mẫu
    for form in pool:
        title = _title_of_form(form).lower()
        if title and title in hay:
            return form
    return ""


def build_classify_prompt(forms: Iterable[str] | None = None) -> str:
    """Prompt NGẮN: chỉ hỏi "ảnh này là biên bản mẫu nào", không đọc số liệu.

    Chạy trước bước đọc chi tiết để biết mỗi ảnh thuộc tờ nào — nhờ vậy 15 ảnh
    lẫn 2 đợt vẫn tách đúng nhóm, và ảnh chụp tem/thiết bị không bị đem đi đọc
    như biên bản.
    """
    forms = [f for f in (forms or sorted(FORM_GROUPS))]
    lines = [f'{f}: {_title_of_form(f)}' for f in forms]
    return (
        "Bạn là chuyên viên nhập liệu của CÔNG TY CP THÍ NGHIỆM ĐIỆN TOÀN CẦU.\n"
        "Nhiệm vụ: với MỖI ảnh, cho biết nó là tờ biên bản nào. KHÔNG đọc số liệu.\n"
        "\n"
        "Các tờ biên bản có thể gặp (mã: tiêu đề in trên tờ):\n"
        + "\n".join(lines)
        + "\n\n"
        "Quy tắc:\n"
        "1. Nhìn TIÊU ĐỀ ở giữa tờ giấy (chữ hoa, to) để quyết định.\n"
        "2. Không thấy tiêu đề thì nhìn bảng: cột nào có mặt thì suy ra tờ đó.\n"
        "3. Ảnh không phải biên bản (chụp tem, công tơ, tủ điện, mặt bằng…): "
        "form = \"\"\n"
        "4. Ảnh chỉ là PHẦN DƯỚI của một tờ (trang 2/2): đọc số hiệu ở góc hoặc "
        "nội dung còn lại; không chắc thì để \"\" và ghi lý do.\n"
        "5. Trả về JSON thuần:\n"
        '{\"photos\": [{\"image_index\": 0, \"form\": \"44\", '
        '\"title\": \"chữ trên tờ\", \"confidence\": \"high\"|\"medium\"|\"low\", '
        '\"reason\": \"vì sao\"}]}\n'
    )


def classify_images(
    images: list[bytes],
    *,
    key: str | None = None,
    model: str | None = None,
    forms: Iterable[str] | None = None,
    max_tokens: int = 2048,
) -> list[dict]:
    """Hỏi model mỗi ảnh là tờ biên bản nào. Lỗi thì trả về danh sách rỗng."""
    if not images:
        return []
    try:
        raw = call_gemini(images, key=key, model=model, forms=forms,
                          prompt_override=build_classify_prompt(forms),
                          max_tokens=max_tokens)
    except GeminiError:
        return []
    photos = raw.get("photos")
    if not isinstance(photos, list):
        photos = (raw.get("reports") if isinstance(raw.get("reports"), list) else [])
    out: list[dict] = []
    for item in photos:
        if not isinstance(item, dict):
            continue
        form = str(item.get("form") or item.get("report_type") or "").strip()
        if form not in TEMPLATES:
            form = ""
        raw_idx = item.get("image_index")
        try:
            idx = int(raw_idx)
        except (TypeError, ValueError):
            idx = -1
        out.append({"image_index": idx, "form": form,
                    "title": str(item.get("title") or ""),
                    "confidence": str(item.get("confidence") or ""),
                    "reason": str(item.get("reason") or "")})
    return out


def group_by_form(photos: list[dict]) -> dict[str, list[int]]:
    """Gom ``image_index`` theo mẫu; ảnh không nhận ra nằm ở khoá ``""``."""
    groups: dict[str, list[int]] = {}
    for ph in photos or []:
        idx = ph.get("image_index", -1)
        if not isinstance(idx, int) or idx < 0:
            continue
        groups.setdefault(ph.get("form") or "", []).append(idx)
    for v in groups.values():
        v.sort()
    return groups


# --------------------------------------------------------------------------- #
# Gọi API
# --------------------------------------------------------------------------- #
def resolve_key(explicit: str | None = None) -> str:
    key = (explicit or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        raise GeminiError(
            "Chưa có API key Gemini. Đặt biến môi trường GEMINI_API_KEY khi chạy "
            "server, hoặc dán key vào ô “API key Gemini” trên giao diện."
        )
    return key


def _request(url: str, *, data: dict | None = None, method: str = "GET") -> dict:
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            payload = json.loads(exc.read().decode())
            detail = (payload.get("error") or {}).get("message") or ""
        except Exception:
            pass
        if exc.code in (400, 403):
            # key sai hoặc model không tồn tại: thử key/model khác vẫn có ích
            # (mỗi key có danh sách model được phép khác nhau)
            raise GeminiBusy(
                "API key không hợp lệ hoặc không có quyền dùng model này"
                + (f" ({detail})" if detail else ""), status=exc.code) from exc
        if exc.code == 404 or _GONE.search(detail):
            # Model đã bị khai tử với key này (Google đổi tên liên tục) → thử model kế
            raise GeminiBusy(
                f"Model không còn dùng được ({detail or 'lỗi 404'})",
                status=404) from exc
        if exc.code in _RETRY_STATUS:
            reason = {429: "đã vượt hạn mức (429)",
                      500: "lỗi máy chủ (500)", 502: "cổng lỗi (502)",
                      503: "đang quá tải (503)", 504: "quá thời gian (504)"}[exc.code]
            raise GeminiBusy(f"Gemini {reason}. Thử lại sau ít phút.",
                             status=exc.code) from exc
        raise GeminiError(f"Gemini trả về lỗi {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise GeminiBusy(f"Không kết nối được tới Gemini: {exc.reason}", status=0) from exc
    except TimeoutError as exc:
        raise GeminiBusy("Gemini phản hồi quá lâu (timeout).", status=408) from exc
    except (ConnectionError, OSError) as exc:
        raise GeminiBusy(f"Mất kết nối tới Gemini: {exc}", status=0) from exc


def list_models(key: str | None = None) -> list[str]:
    """Các model hỗ trợ ``generateContent`` – cho dropdown trên giao diện."""
    key = resolve_key(key)
    data = _request(f"{GEMINI_BASE}/models?key={key}&pageSize=200")
    out = []
    for m in data.get("models", []):
        name = (m.get("name") or "").removeprefix("models/")
        methods = m.get("supportedGenerationMethods") or []
        if "generateContent" in methods and name.startswith("gemini"):
            out.append(name)

    return sorted(out, key=_model_rank, reverse=True)


_VER = re.compile(r"gemini-(\d+(?:\.\d+)?)")


def _model_rank(name: str) -> tuple:
    """Xếp model tốt nhất lên đầu: ổn định > preview, bản mới > bản cũ.

    Google đổi tên model liên tục nên phải xếp hạng động, không ghim cứng.
    Model chuyên dụng (ảnh, TTS, live, embedding…) bị đẩy xuống cuối.
    """
    low = name.lower()
    specialized = any(k in low for k in ("image", "tts", "audio", "live", "embedding",
                                        "embed", "veo", "imagen", "nano-banana",
                                        "computer-use", "robotics", "omni", "transcribe"))
    m = _VER.search(low)
    ver = float(m.group(1)) if m else 0.0
    stable = "-preview" not in low and "-exp" not in low
    return (
        not specialized,                       # 1. model biết đọc ảnh/chữ trước
        ver,                                   # 2. đời mới trước (3.x > 2.5)
        stable,                                # 3. cùng đời: bản ổn định trước
        "lite" not in low,                     # 4. bản đầy đủ trước bản lite
        "flash" in low,                        # 5. flash (nhanh, rẻ) trước pro
        name,
    )


AUTO_MODEL_CACHE: dict[str, str] = {}


def auto_model(key: str | None = None) -> str:
    """Model mới nhất mà **key này** dùng được (dò 1 lần, sau đó lấy cache).

    Nhờ vậy khi Google khai tử model, tool tự chuyển sang model kế tiếp thay vì
    báo lỗi 404 cho người dùng. Mất mạng / key sai → rơi về :data:`SAFE_MODEL`.
    """
    k = resolve_key(key)
    if k in AUTO_MODEL_CACHE:
        return AUTO_MODEL_CACHE[k]
    try:
        models = list_models(k)
    except Exception:          # offline / key sai / phản hồi lạ → vẫn phải chạy
        return SAFE_MODEL
    best = (models or [SAFE_MODEL])[0]
    AUTO_MODEL_CACHE[k] = best
    return best


def forget_model(key: str | None = None) -> None:
    """Xoá cache model (dùng khi model đang dùng vừa bị khai tử)."""
    if key:
        AUTO_MODEL_CACHE.pop(key, None)
    else:
        AUTO_MODEL_CACHE.clear()


def _wire_model(model: str) -> str:
    model = (model or DEFAULT_MODEL).strip().removeprefix("models/")
    if model and _RETIRED.match(model):
        return ""            # tên đã khai tử -> để call_gemini tự dò model mới
    return model


def _is_gemini3(model: str) -> bool:
    """Model thuộc dòng Gemini 3 (có ``thinkingConfig``)."""
    return bool(re.search(r"gemini-3", (model or "").lower()))


def parse_json_loose(text: str) -> dict:
    """Bóc JSON khỏi câu trả lời (kể cả khi bị bọc ```json … ```).

    **Luôn trả về ``dict``.** Model đôi khi trả thẳng một *mảng* biên bản
    (``[{...}, {...}]``) hoặc bọc trong ``{"reports": [...]}``; cả hai đều được
    quy về một object để phần sau khỏi phải kiểm tra kiểu. Trước đây mảng lọt
    xuống dưới và gây ``'list' object has no attribute 'get'``.
    """
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    def _load(candidate: str):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    got = _load(text)
    if got is None:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            got = _load(text[start:end + 1])
        if got is None:
            # có thể là mảng trần bị cắt mất dấu ngoặc
            start, end = text.find("["), text.rfind("]")
            if start >= 0 and end > start:
                got = _load(text[start:end + 1])

    if isinstance(got, (dict, list)):
        return _as_result_object(got)
    raise GeminiFatal(
        "Gemini trả về JSON không hợp lệ (có thể bị cắt vì hết token). "
        "Thử lại với ít ảnh hơn hoặc chọn model flash."
    )


def _as_result_object(value) -> dict:
    """Quy mọi dạng JSON hợp lý về ``{"reports": [...]}``."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, list):
        return {}
    items = [v for v in value if isinstance(v, dict)]
    # mảng các biên bản: phần tử có "report_type"/"data"/"rows"
    if any(("report_type" in v) or ("data" in v) or ("rows" in v) for v in items):
        return {"reports": items}
    # mảng lồng một phần tử: [{"reports": [...]}]
    if len(items) == 1:
        return items[0]
    return {"reports": items}


def call_gemini(
    images: list[bytes],
    *,
    key: str | None = None,
    model: str | None = None,
    forms: Iterable[str] | None = None,
    prompt_override: str | None = None,
    max_tokens: int = MAX_OUTPUT_TOKENS,
    fallbacks: list[str] | None = None,
    alt_keys: list[str] | None = None,
    on_try=None,
) -> dict:
    """Gửi ảnh cho Gemini, tự chuyển phương án khi model bận.

    Chuỗi dự phòng (theo yêu cầu của công ty **chỉ trong Gemini**, không cần
    tài khoản khác)::

        1. model chính             + key chính
        2. model dự phòng          + key chính
        3. model chính             + key dự phòng   (nếu có)
        4. model dự phòng          + key dự phòng

    Chỉ chuyển bước khi lỗi thuộc loại "thử lại được" (429 / 5xx / timeout /
    mất mạng / key không có quyền với model đó). Lỗi nội dung (ảnh hỏng, JSON
    rỗng) thì dừng ngay để báo đúng cho người dùng.

    ``on_try(buoc, model, key_slot, exc)`` được gọi sau mỗi lần thất bại — dùng
    để ghi nhật ký cho giao diện.

    ``prompt_override`` cho phép dùng lại đường gửi ảnh này cho việc khác
    (ví dụ bước soát số liệu trong :mod:`bienban.checks`).
    """
    key = resolve_key(key)
    keys = [key] + [k for k in (alt_keys or []) if k and k != key]

    def _models_for(first_key: str) -> list[str]:
        """Chuỗi model: model mới nhất (hoặc tên người dùng chọn) → dự phòng."""
        out: list[str] = []
        primary = _wire_model(model or DEFAULT_MODEL)
        if not primary:
            # Không ai chỉ định model (hoặc tên đã bị khai tử) → hỏi Google xem
            # key này còn dùng được model nào, rồi mới đến danh sách dự phòng.
            primary = auto_model(first_key)
        if primary:
            out.append(primary)
        for m in list(fallbacks or []):
            m = _wire_model(m)
            if m and m not in out:
                out.append(m)
        return out or [SAFE_MODEL]

    def _run(models: list[str]) -> dict:
        steps = [(m, k) for k in keys for m in models]   # key chính trước
        nonlocal last
        for idx, (m, k) in enumerate(steps, start=1):
            try:
                return _attempt(images, key=k, model=m, forms=forms,
                                prompt_override=prompt_override, max_tokens=max_tokens)
            except GeminiBusy as exc:
                last = exc
                if on_try:
                    on_try(idx, m, "chính" if k == key else "dự phòng", exc)
                continue
            except GeminiFatal:
                raise
        raise GeminiError(f"Không gọi được model nào (lỗi cuối: {last})") from last

    last: GeminiError | None = None
    models = _models_for(key)
    try:
        return _run(models)
    except GeminiError:
        # Chỉ khi lỗi là "model đã bị khai tử" (404) mới dò lại model mới nhất.
        # Lỗi khác (429, mất mạng…) thì dò lại cũng vô ích và còn tốn 1 lượt gọi.
        if not (last and getattr(last, "status", 0) == 404):
            raise
        forget_model(key)
        fresh = auto_model(key)
        if fresh in models:
            raise
        if on_try:
            on_try(len(models) + 1, fresh, "tự dò", last)
        return _run([fresh])


def _attempt(
    images: list[bytes],
    *,
    key: str,
    model: str,
    forms: Iterable[str] | None = None,
    prompt_override: str | None = None,
    max_tokens: int = MAX_OUTPUT_TOKENS,
) -> dict:
    """Một lần gửi ảnh cho một model + một key."""
    if not images:
        raise GeminiFatal("Chưa có ảnh nào để nhận dạng")
    if len(images) > MAX_IMAGES:
        raise GeminiFatal(f"Chỉ gửi tối đa {MAX_IMAGES} ảnh một lần")
    prompt = prompt_override or build_prompt(forms)

    parts: list[dict] = [{"text": prompt}]
    for i, blob in enumerate(images):
        mime, b64 = prepare_image(blob)
        parts.append({"text": f"image_index = {i}"})
        parts.append({"inline_data": {"mime_type": mime, "data": b64}})

    gen_cfg: dict = {
        "temperature": 0.1,
        "responseMimeType": "application/json",
        "maxOutputTokens": max(max_tokens, MAX_OUTPUT_TOKENS),
    }
    if _is_gemini3(model):
        # Gemini 3 trừ token suy nghĩ vào maxOutputTokens → JSON dài (biên bản 44)
        # dễ bị cắt cụt. Mức "low" là đủ cho việc đọc ảnh theo mẫu.
        gen_cfg["thinkingConfig"] = {"thinkingLevel": "low"}
    payload = {"contents": [{"role": "user", "parts": parts}],
               "generationConfig": gen_cfg}
    url = f"{GEMINI_BASE}/models/{model}:generateContent?key={key}"
    data = _request(url, data=payload, method="POST")

    candidates = data.get("candidates") or []
    if not candidates:
        reason = (data.get("promptFeedback") or {}).get("blockReason")
        raise GeminiFatal(
            "Gemini không trả về kết quả" + (f" (bị chặn: {reason})" if reason else "")
        )
    texts = [
        p.get("text", "")
        for p in ((candidates[0].get("content") or {}).get("parts") or [])
        if isinstance(p, dict)
    ]
    raw = "".join(texts).strip()
    if not raw:
        finish = candidates[0].get("finishReason")
        hint = ""
        if finish == "MAX_TOKENS":
            hint = (" — bị cắt vì hết token (model Gemini 3 dùng token cho phần suy nghĩ). "
                    "Thử model flash hoặc gửi ít ảnh hơn.")
        raise GeminiFatal(
            "Gemini trả về nội dung rỗng"
            + (f" (finishReason: {finish})" if finish else "") + hint
        )
    return parse_json_loose(raw)


# --------------------------------------------------------------------------- #
# Chuẩn hoá kết quả về đúng JSON của tool
# --------------------------------------------------------------------------- #
_SERIES_HINT = {
    "44": {"r_cuon_day_1_chieu_ohm.cao_ap": 5,
           "r_cuon_day_1_chieu_ohm.ha_ap_mOhm": 2,
           "ti_so_bien_ap.ha_1": 5, "ti_so_bien_ap.ha_2": 5},
    "49": {"r_cuon_day_1_chieu_ohm.cao_ap.ab": 5,
           "r_cuon_day_1_chieu_ohm.cao_ap.bc": 5,
           "r_cuon_day_1_chieu_ohm.cao_ap.ca": 5,
           "ti_so_bien_ap.k1": 5, "ti_so_bien_ap.k2": 5, "ti_so_bien_ap.k3": 5},
}

_FIXED_ROWS = {
    "44": ("r_cach_dien_Mohm", ["cao_vo_ha1", "cao_vo_ha2", "ha1_ha2"]),
    "49": ("r_cach_dien_Mohm", ["cao_vo", "cao_ha", "ha_vo"]),
}


def _deep_set(target: dict, path: list[str], value) -> None:
    cur = target
    for p in path[:-1]:
        cur = cur.setdefault(p, {})
        if not isinstance(cur, dict):
            return
    cur[path[-1]] = value


def _to_list(value, n: int | None) -> list[str]:
    if isinstance(value, dict):
        value = list(value.values())
    if not isinstance(value, list):
        value = [value] if value not in (None, "") else []
    out = [str(v).strip() if v is not None else "" for v in value]
    if n:
        out = (out + [""] * n)[:n]
    return out


def _row_from_mapping(mapping: dict, columns: list[dict], *, stt: bool, index: int) -> dict:
    row: dict[str, str] = {}
    if stt:
        row["stt"] = str(mapping.get("stt") or index + 1)
    for col in columns:
        v = mapping.get(col["key"])
        row[col["key"]] = "" if v is None else str(v).strip()
    return row


def normalize_ai_result(raw, *, forms: Iterable[str] | None = None) -> dict:
    """Đổi JSON của Gemini thành JSON chuẩn của tool.

    Kết quả: ``{"thong_tin_chung": {...}, "bien_ban_44_mba": {...}, ...,
    "_ai": {"notes": [...], "sources": {...}, "context": [...]}}``

    Hàm này chịu được cả JSON hơi lệch: ``data`` dạng phẳng hay lồng, bảng dạng
    list-of-object hay list-of-list, ``bien_ban_45_mccb: {rows: [...]}`` …
    """
    # Gemini có thể trả mảng trần hoặc {"reports": [...]}: quy về dict trước.
    raw = _as_result_object(raw)
    forms = list(forms or sorted(FORM_GROUPS))
    out: dict = {}
    notes: list[str] = []
    sources: dict[str, list[int]] = {}
    context: list[dict] = []

    common = raw.get("thong_tin_chung") or raw.get("common") or {}
    if isinstance(common, dict):
        tt = {k: v for k, v in common.items() if v not in (None, "")}
        if tt:
            out["thong_tin_chung"] = tt

    context = [c for c in (raw.get("context_photos") or []) if isinstance(c, dict)]

    reports = raw.get("reports")
    if not isinstance(reports, list):
        # dạng phẳng: {"bien_ban_44_mba": {...}, ...}
        reports = []
        for form in forms:
            key = DATA_KEYS[form]
            for k in (key, f"bien_ban_{form}", f"report_{form}", form):
                if isinstance(raw.get(k), dict):
                    reports.append({"report_type": form, "data": raw[k], "_key": k})
                    break

    for rep in reports:
        if not isinstance(rep, dict):
            continue
        form = str(rep.get("report_type") or rep.get("type") or rep.get("_key") or "").strip()
        form = form.replace("bien_ban_", "")[:2]
        if form not in FORM_GROUPS:
            continue
        block = rep.get("data")
        if not isinstance(block, dict):
            block = {k: v for k, v in rep.items()
                     if k not in ("report_type", "type", "source_image_indices",
                                  "ai_notes", "confidence", "thong_tin_chung", "common")}
        block = dict(block)
        block.pop("thong_tin_chung", None)

        # gộp thông tin chung của biên bản vào khoá chung
        rep_common = rep.get("thong_tin_chung") or rep.get("common")
        if isinstance(rep_common, dict) and rep_common:
            merged = dict(out.get("thong_tin_chung") or {})
            for k, v in rep_common.items():
                if v not in (None, "") and not merged.get(k):
                    merged[k] = v
            if merged:
                out["thong_tin_chung"] = merged

        # --- bảng ---------------------------------------------------------
        for title, table in _tables(form):
            src_key, src = _table_source(block, table)
            if src is None:
                continue
            if table.get("kind") == "fixed":
                rows = []
                for rk in table["rows"]:
                    rk = rk["key"] if isinstance(rk, dict) else rk
                    item = (src or {}).get(rk) if isinstance(src, dict) else None
                    rows.append(_row_from_mapping(item or {}, table["columns"],
                                                  stt=False, index=0) | {"key": rk})
                block[table["key"]] = {"rows": rows}
                continue
            if isinstance(src, dict):
                src = src.get("rows") or src.get("ket_qua_thu_nghiem") or list(src.values())
            if not isinstance(src, list):
                continue
            rows = []
            for i, item in enumerate(src):
                if isinstance(item, dict):
                    rows.append(_row_from_mapping(item, table["columns"],
                                                  stt=bool(table.get("stt")), index=i))
                elif isinstance(item, (list, tuple)):
                    if table.get("stt"):
                        rows.append(_row_from_mapping(
                            dict(zip([c["key"] for c in table["columns"]], item)),
                            table["columns"], stt=False, index=i) | {"stt": str(i + 1)})
                    else:
                        rows.append(_row_from_mapping(
                            dict(zip([c["key"] for c in table["columns"]], item)),
                            table["columns"], stt=False, index=i))
                elif isinstance(item, str):
                    cols = [c["key"] for c in table["columns"]]
                    vals = [v.strip() for v in item.split("|")]
                    rows.append(_row_from_mapping(dict(zip(cols, vals)), table["columns"],
                                                  stt=bool(table.get("stt")), index=i))
            if rows:
                block[table["key"]] = {"rows": rows}
                if src_key and src_key != table["key"]:
                    block.pop(src_key, None)

        # --- dãy số cố định ----------------------------------------------
        for path_s, n in _SERIES_HINT.get(form, {}).items():
            path = path_s.split(".")
            cur = block
            for p in path[:-1]:
                cur = cur.get(p) if isinstance(cur, dict) else None
                if cur is None:
                    break
            if isinstance(cur, dict) and path[-1] in cur:
                cur[path[-1]] = _to_list(cur[path[-1]], n)

        # --- dữ liệu kiểu cũ (ô phẳng) -> rows[] -------------------------
        if not _has_rows(block, form):
            legacy = _legacy_rows(form, block)
            if legacy:
                table = next(t for _, t in _tables(form) if t.get("kind") == "rows")
                block[table["key"]] = {"rows": legacy}

        # --- mẫu 48: 1 dòng phẳng -> rows[] ------------------------------
        if form == "48":
            if not block.get("rows") and any(block.get(k) for k in
                                             ("chi_danh", "gia_tri_do_Ohm", "gia_tri_do")):
                block["rows"] = {"rows": [{
                    "stt": "1",
                    "chi_danh": block.get("chi_danh") or "",
                    "ket_noi_trung_tinh": block.get("ket_noi_trung_tinh") or "",
                    "loai_tiep_dat": block.get("loai_tiep_dat") or "",
                    "gia_tri_do": block.get("gia_tri_do_Ohm") or block.get("gia_tri_do") or "",
                }]}

        for k in ("thiet_bi_do", "ket_luan", "chi_danh", "so_luong", "so_bien_ban",
                  "hieu", "loai", "kieu", "hieu_may", "so_tem", "so_may"):
            if isinstance(block.get(k), (int, float)):
                block[k] = str(block[k])

        notes.extend(str(n) for n in (rep.get("ai_notes") or []))
        idx = rep.get("source_image_indices") or []
        src_idx = [int(i) for i in idx if isinstance(i, (int, float))]

        key = DATA_KEYS[form]
        if key not in out:
            out[key] = block
        else:
            # ĐÃ CÓ biên bản cùng mẫu → KHÔNG ghi đè (trước đây biên bản thứ 2
            # của cùng mẫu bị mất sạch). Gom vào danh sách "_extra" để bộ sinh
            # in thêm một bản riêng cho từng biên bản.
            extra = out.setdefault("_extra", {}).setdefault(key, [])
            extra.append(block)
            notes.append(
                f"Mẫu {form}: có {len(extra) + 1} biên bản cùng loại — "
                f"mỗi biên bản in thành một file riêng")
        if src_idx:
            sources.setdefault(form, [])
            sources[form] = sorted(set(sources[form]) | set(src_idx))

    out["_ai"] = {"notes": notes, "sources": sources, "context": context}
    return out


def _tables(form: str):
    from .schema import tables_of
    return list(tables_of(form))


def _has_rows(block: dict, form: str) -> bool:
    for _, t in _tables(form):
        if t.get("kind") != "rows":
            continue
        val = block.get(t["key"])
        if isinstance(val, dict) and val.get("rows"):
            return True
        if isinstance(val, list) and val:
            return True
    return False


def _legacy_rows(form: str, block: dict) -> list[dict]:
    """Dữ liệu do con người nhập tay (ô phẳng) → một dòng bảng."""
    if form == "45":
        r = block.get("r_cach_dien_Mohm") or {}
        tx = block.get("r_tiep_xuc_uohm") or {}
        if not (r or tx):
            return []
        return [{
            "stt": "1",
            "rcd_close": r.get("close", ">5000"),
            "rcd_open": r.get("open", ">5000"),
            "rtx_a": tx.get("pha_a", ""), "rtx_b": tx.get("pha_b", ""),
            "rtx_c": tx.get("pha_c", ""),
            "utest": block.get("u_test_kV", "3"),
            "dong_cat": block.get("dong_cat_s", "5"),
            "ket_qua": block.get("ket_qua", "Đạt"),
            "so_tem": block.get("so_tem", ""),
        }]
    if form == "46":
        if not block.get("r_cach_dien_Mohm"):
            return []
        return [{"doi_tuong_do": block.get("chi_danh") or "LA 01",
                 "r_cach_dien": block.get("r_cach_dien_Mohm", ""),
                 "dong_ro": block.get("dong_ro_uA", ""),
                 "u_ac": block.get("u_ac_tang_cao_kV", "")}]
    if form == "47":
        r = block.get("r_cach_dien_Mohm") or {}
        u = block.get("u_ac_tang_cao_kV") or {}
        if not (r or u):
            return []
        return [{"thiet_bi": block.get("chi_danh") or "FCO 01",
                 "rcd_truoc": r.get("truoc_thu", ">10000"),
                 "rcd_sau": r.get("sau_thu", ">10000"),
                 "ac_kho": u.get("kho", "60"), "ac_uot": u.get("uot", "50"),
                 "dong_cat": block.get("dong_cat_s", "5"),
                 "ket_qua": block.get("ket_qua", "Đạt")}]
    return []


def _table_source(block: dict, table: dict):
    """Tìm dữ liệu bảng trong block, chấp nhận vài tên khoá quen thuộc."""
    for key in (table["key"], "ket_qua_thu_nghiem", f"{table['key']}_rows"):
        val = block.get(key)
        if isinstance(val, list) and val:
            return key, val
        if isinstance(val, dict) and val.get("rows"):
            return key, val
    return None, None
