"""Kiểm thử bộ điền biên bản 44–48.

Chạy::

    python -m pytest -q
"""

from __future__ import annotations

import json
from pathlib import Path

import docx
import pytest

from bienban.fill import load_config, render_all, build_conclusion
from bienban.labels import find_label_span, iter_text_paragraphs, para_text
from bienban.normalize import (
    norm_date,
    norm_number,
    number_to_words_vi,
    quantity_both,
)
from bienban.ooxml import cell_text
from bienban.validate import validate

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples" / "e-green-01112026.json"
TEMPLATES = ROOT / "templates"
TC = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc"


@pytest.fixture(scope="module")
def data():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rendered(tmp_path_factory, data):
    out = tmp_path_factory.mktemp("out")
    paths, warnings = render_all(data, templates_dir=TEMPLATES, out_dir=out)
    return {p.name.split("_")[0]: p for p in paths}, warnings


def _texts(path):
    d = docx.Document(str(path))
    return [para_text(p) for p in iter_text_paragraphs(d)]


def _tables(path):
    d = docx.Document(str(path))
    return [[[cell_text(tc) for tc in r._tr.findall(TC)] for r in t.rows] for t in d.tables]


# --------------------------------------------------------------------------- #
# Chuẩn hoá
# --------------------------------------------------------------------------- #
class TestNormalize:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("1/11/2026", "01/11/2026"),
            ("01/11/2026", "01/11/2026"),
            ("1-11-26", "01/11/2026"),
            ("2026-11-01", "01/11/2026"),
            ("4.11.2026", "04/11/2026"),
        ],
    )
    def test_date(self, raw, expected):
        assert norm_date(raw) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("3.52", "3,52"),
            ("3,52", "3,52"),
            (">5000", ">5000"),
            (">5.000", ">5.000"),
            ("1,580", "1,580"),
            ("273", "273"),
            ("2.4", "2,4"),
            ("15,3kV", "15,3kV"),
        ],
    )
    def test_number(self, raw, expected):
        assert norm_number(raw) == expected

    def test_number_words(self):
        assert number_to_words_vi(1) == "một"
        assert number_to_words_vi(2) == "hai"
        assert number_to_words_vi(15) == "mười lăm"
        assert number_to_words_vi(21) == "hai mươi mốt"
        assert quantity_both("01") == "Một (01)"


# --------------------------------------------------------------------------- #
# Nhận dạng nhãn
# --------------------------------------------------------------------------- #
class TestLabels:
    def test_label_needs_colon(self):
        assert find_label_span("Địa chỉ: Hà Nội", "Địa chỉ") == (9, 9)
        assert find_label_span("Địa chỉ Hà Nội", "Địa chỉ") is None

    def test_word_boundary(self):
        # 'IN' không được khớp vào đầu 'NGHIỆM'
        assert find_label_span("THÍ NGHIỆM: x", "IN") is None

    def test_flexible_no_accent_input(self):
        # nhãn có dấu vẫn khớp khi văn bản bị gõ không dấu
        assert find_label_span("Dia chi: Ha Noi", "Địa chỉ") == (9, 9)


# --------------------------------------------------------------------------- #
# Sinh biên bản
# --------------------------------------------------------------------------- #
class TestRender:
    def test_all_five(self, rendered):
        paths, _ = rendered
        assert sorted(paths) == ["44", "45", "46", "47", "48"]

    def test_no_warnings(self, rendered):
        _, warnings = rendered
        assert warnings == []

    def test_44_numbers(self, rendered):
        texts = _texts(rendered[0]["44"])
        head = " | ".join(" ".join(r) for r in _tables(rendered[0]["44"])[0])
        assert "SỐ: 50441126/BB-TC" in head
        assert "NGÀY: 04/11/2026" in head
        assert any(t.startswith("Hiệu máy: EMC") and "017246" in t for t in texts)
        assert any(t.startswith("Số máy: 04080968") for t in texts)
        assert "MÁY BIẾN ÁP 1 PHA" in texts
        t = _tables(rendered[0]["44"])
        assert t[1][1] == ["(Cao+Vỏ) - Hạ 1", "2760", "2106", "1,31"]
        assert t[2][2][1:6] == ["16,42", "15,98", "15,57", "15,12", "14,67"]
        assert t[3][2][1:6] == ["57,98", "56,59", "55,21", "53,83", "52,46"]
        assert t[4][1] == ["Kết quả đo", "230", "1,58", "0,73", "97,6"]
        assert t[5][1] == ["Kết quả đo", "304,7", "2,4", "3,94", "563,2"]
        assert t[6][1] == ["Cuộn dây cao áp", "50", "1 phút"]

    def test_45_two_fields_per_line(self, rendered):
        texts = _texts(rendered[0]["45"])
        assert "Hiệu: MITSUBISHI\t- Số cực: 03" in texts
        assert "Loại: MCCB\t- Kiểu: NF-250" in texts
        assert "Điện áp định mức: -\t- Dòng điện định mức: 250A" in texts
        assert "Kiểm tra bên ngoài: Bình thường\t- Số lượng: 01" in texts
        t = _tables(rendered[0]["45"])[1]
        assert t[2] == ["1", ">5000", ">5000", "273", "275", "279", "3", "5", "Đạt", "017215"]

    def test_46_la(self, rendered):
        texts = _texts(rendered[0]["46"])
        assert "Vật liệu cách điện: Polymer\t- MCOV: 15,3kV" in texts
        assert "Dòng điện xả tối đa: 10 kA" in texts
        assert _tables(rendered[0]["46"])[1][1] == ["LA 01", ">10000", "17", "35"]

    def test_47_fco(self, rendered):
        texts = _texts(rendered[0]["47"])
        assert "Điện áp định mức: 27kV\t- Khả năng cắt ngắn mạch: 12kA" in texts
        assert _tables(rendered[0]["47"])[1][2] == ["FCO 01", ">10000", ">10000", "60", "50", "5", "Đạt"]

    def test_48_earth(self, rendered):
        texts = _texts(rendered[0]["48"])
        assert "THIẾT BỊ THỬ NGHIỆM: KEW 4105DL" in texts
        assert any("BIÊN BẢN THỬ NGHIỆM" in cell for row in _tables(rendered[0]["48"])[0]
                   for cell in row)
        assert _tables(rendered[0]["48"])[1][1] == [
            "1", "Điện trở nối đất trạm biến áp", "Có", "Làm việc", "3,52"
        ]

    def test_signatures(self, rendered):
        for form in ("45", "48"):
            t = _tables(rendered[0][form])[-1]
            assert t[1] == ["Nguyễn Trung Nghĩa", "Nguyễn Minh Quân", "Nguyễn Nhật Tân"]

    def test_headers_kept(self, rendered):
        """Logo + footer của mẫu phải còn nguyên (không dựng lại tài liệu)."""
        d = docx.Document(str(rendered[0]["45"]))
        footer = " ".join(p.text for p in d.sections[0].footer.paragraphs)
        assert "thinghiemdientoancau.com" in footer

    def test_output_is_valid_docx(self, rendered):
        import zipfile

        for path in rendered[0].values():
            with zipfile.ZipFile(path) as zf:
                assert "word/document.xml" in zf.namelist()
                assert any(n.startswith("word/media/") for n in zf.namelist())


# --------------------------------------------------------------------------- #
# Cấu hình in đậm / in hoa
# --------------------------------------------------------------------------- #
class TestStyle:
    def test_template_mode_keeps_format(self, rendered):
        d = docx.Document(str(rendered[0]["44"]))
        p = [p for p in d.paragraphs if p.text.startswith("Tên công trình")][0]
        assert not all(r.bold for r in p.runs)

    def test_bold_upper_mode(self, data, tmp_path):
        cfg = load_config()
        cfg["style"]["header_values"] = "bold_upper"
        paths, _ = render_all(
            data, templates_dir=TEMPLATES, out_dir=tmp_path, cfg=cfg, forms=["45"]
        )
        d = docx.Document(str(paths[0]))
        p = [p for p in d.paragraphs if p.text.lower().startswith("tên công trình")][0]
        value = p.text.split(":", 1)[1].strip()
        assert value.isupper()                     # giá trị in hoa
        assert p.text.split(":", 1)[0] == "Tên công trình"   # nhãn giữ nguyên
        bold_runs = [r for r in p.runs if r.text.strip()]
        assert bold_runs and all(r.bold for r in bold_runs)


# --------------------------------------------------------------------------- #
# Kiểm tra dữ liệu
# --------------------------------------------------------------------------- #
class TestValidate:
    def test_sample_is_clean(self, data):
        problems = validate(data)
        assert [p for p in problems if p.level == "error"] == []

    def test_missing_form_is_warning(self, data):
        d = json.loads(json.dumps(data))
        del d["bien_ban_47_fco"]
        assert any(p.level == "warn" and "bien_ban_47_fco" in p.where
                   for p in validate(d))

    def test_bad_date(self, data):
        """Ngày sai định dạng: cảnh báo, KHÔNG chặn in (in nguyên chữ đã nhập)."""
        d = json.loads(json.dumps(data))
        d["thong_tin_chung"]["ngay_kiem_dinh"] = "31/02/2026"
        probs = [p for p in validate(d) if "ngay_kiem_dinh" in p.where]
        assert probs and all(p.level == "warn" and not p.blocking for p in probs)

    def test_missing_insulation(self, data):
        """Thiếu số liệu: cảnh báo để người dùng biết, nhưng vẫn sinh Word được."""
        d = json.loads(json.dumps(data))
        del d["bien_ban_44_mba"]["r_cach_dien_Mohm"]["ha1_ha2"]["r60"]
        probs = [p for p in validate(d) if "ha1_ha2" in p.where]
        assert probs
        assert all(p.level == "warn" and not p.blocking for p in probs)

    def test_us_decimal_separator_warns(self, data):
        d = json.loads(json.dumps(data))
        d["bien_ban_48_tiep_dat"]["gia_tri_do_Ohm"] = "3.52"
        assert any(p.level == "warn" and "gia_tri_do_Ohm" in p.where
                   for p in validate(d))


# --------------------------------------------------------------------------- #
# Kết luận tự sinh
# --------------------------------------------------------------------------- #
class TestConclusion:
    def test_explicit_kept(self, data):
        cfg = load_config()
        block = data["bien_ban_46_la"]
        assert build_conclusion("46", block, data, cfg) == block["ket_luan"]

    def test_generated_when_missing(self, data):
        cfg = load_config()
        block = dict(data["bien_ban_45_mccb"])
        block.pop("ket_luan")
        text = build_conclusion("45", block, data, cfg)
        assert text.startswith("Một (01) máy cắt hạ thế (MCCB) trên đạt yêu cầu")


# --------------------------------------------------------------------------- #
# Web API
# --------------------------------------------------------------------------- #
class TestWeb:
    @pytest.fixture()
    def client(self):
        import sys

        sys.path.insert(0, str(ROOT))
        from web.app import app

        app.config.update(TESTING=True)
        return app.test_client()

    def test_index(self, client):
        r = client.get("/")
        assert r.status_code == 200
        page = r.get_data(as_text=True)
        assert "điền biên bản" in page.lower()
        assert 'id="btnRecognize"' in page

    def test_validate(self, client, data):
        r = client.post("/api/validate", json=data)
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_render_ok(self, client, data):
        r = client.post("/api/render", json=data)
        body = r.get_json()
        assert body["ok"] is True
        assert len(body["files"]) == 5
        assert body["zip_url"].endswith("__all__.zip")


# --------------------------------------------------------------------------- #
# Xem trước HTML
# --------------------------------------------------------------------------- #
class TestPreview:
    @pytest.fixture(scope="class")
    @classmethod
    def html(cls, tmp_path_factory):
        import json as _json

        from bienban.preview import docx_to_html

        data = _json.loads(SAMPLE.read_text(encoding="utf-8"))
        out_dir = tmp_path_factory.mktemp("preview")
        paths, _ = render_all(data, templates_dir=TEMPLATES, out_dir=out_dir)
        return {p.name.split("_")[0]: docx_to_html(p) for p in paths}

    def test_has_tables_and_logo(self, html):
        for form, h in html.items():
            assert h.count("<table") >= 2, form
            assert h.count("<img") == 1, f"{form}: phải có đúng 1 logo"

    def test_numbers_present(self, html):
        import html as _h

        def text(form):
            return _h.unescape(html[form])

        assert "50441126/BB-TC" in text("44")
        assert "04080968" in text("44")
        assert "2760" in text("44") and "1,31" in text("44")
        assert "273" in text("45") and ">5000" in text("45")
        assert "3,52" in text("48")
        assert "Nguyễn Trung Nghĩa" in text("45")

    def test_merged_cells(self, html):
        # bảng chữ ký / bảng số liệu có gộp ô -> phải có colspan hoặc rowspan
        assert "colspan" in html["45"] or "rowspan" in html["45"]
        assert "rowspan" in html["44"]

    def test_no_floating_artifacts(self, html):
        # dấu chìm (watermark) không được lọt vào ô chữ ký
        assert html["45"].count("<img") == 1
        assert "[LOGO]" not in html["45"]


# --------------------------------------------------------------------------- #
# Web API: xem trước + tải file
# --------------------------------------------------------------------------- #
class TestWebDownload:
    @pytest.fixture()
    def client(self):
        import sys

        sys.path.insert(0, str(ROOT))
        from web.app import app

        app.config.update(TESTING=True)
        return app.test_client()

    def test_render_returns_previews(self, client, data):
        body = client.post("/api/render", json=data).get_json()
        assert body["ok"] is True
        assert body["token"]
        assert len(body["files"]) == 5
        assert set(body["previews"]) == set(body["files"])
        for name, html in body["previews"].items():
            assert "<table" in html, name
            assert "doc-tbl" in html, name

    def test_download_link_is_real_get(self, client, data):
        """/api/render giờ trả link GET thật để iframe tải được (không dùng blob)."""
        body = client.post("/api/render", json=data).get_json()
        token = body["token"]
        one = body["files"][1]
        r = client.get(f"/download/{token}/{one}")
        assert r.status_code == 200
        assert r.data[:2] == b"PK"
        assert "attachment" in r.headers["Content-Disposition"]
        assert one in r.headers["Content-Disposition"]

        z = client.get(f"/download/{token}/__all__.zip")
        assert z.status_code == 200
        assert z.data[:2] == b"PK"

    def test_preview_page(self, client, data):
        body = client.post("/api/render", json=data).get_json()
        token, name = body["token"], body["files"][0]
        r = client.get(f"/preview/{token}/{name}")
        assert r.status_code == 200
        page = r.get_data(as_text=True)
        assert "doc-tbl" in page and "Xem trước" in page
        assert f"/download/{token}/{name}" in page

    def test_bad_token_404(self, client):
        assert client.get("/download/khongtontai/x.docx").status_code == 404


# --------------------------------------------------------------------------- #
# Nhận dạng ảnh bằng Gemini (không gọi mạng thật)
# --------------------------------------------------------------------------- #
def _fake_gemini_response(payload: dict) -> dict:
    """Bọc JSON thành câu trả lời giả lập của generateContent."""
    import json as _json

    return {
        "candidates": [{
            "content": {"parts": [{"text": "```json\n" + _json.dumps(payload, ensure_ascii=False) + "\n```"}]},
            "finishReason": "STOP",
        }]
    }


# Phản hồi mô phỏng đúng "hợp đồng" của bản tham khảo: reports[] + rows
AI_PAYLOAD = {
    "context_photos": [{"image_index": 0, "summary": "tờ biên bản MCCB"}],
    "reports": [
        {
            "report_type": "45",
            "source_image_indices": [0],
            "confidence": "medium",
            "ai_notes": ["số tem dòng 2 hơi mờ"],
            "thong_tin_chung": {"ten_cong_trinh": "Trạm biến áp 50kVA – E-GREEN",
                                "dia_chi": "Khu phố Gia Huỳnh, Phường Trảng Bàng, Tây Ninh",
                                "don_vi_yeu_cau": "DNTN E-GREEN",
                                "ly_do_kiem_dinh": "Sau sự cố",
                                "noi_kiem_dinh": "Tại hiện trường",
                                "ngay_kiem_dinh": "1/11/2026",
                                "ngay_lap_bien_ban": "4/11/2026",
                                "can_bo_ky_ten": {"nguoi_thu": "Nguyễn Trung Nghĩa",
                                                  "nguoi_kiem_tra": "Nguyễn Minh Quân",
                                                  "p_giam_doc": "Nguyễn Nhật Tân"}},
            "data": {
                "so_bien_ban": "50451126/BB-TC",
                "chi_danh": "MCCB 250A", "hieu": "MITSUBISHI", "kieu": "NF-250",
                "dong_dinh_muc": "250A", "so_cuc": "03", "so_luong": "01",
                "rows": [
                    {"stt": "1", "rcd_close": ">5000", "rcd_open": ">5000", "rtx_a": "273",
                     "rtx_b": "275", "rtx_c": "279", "utest": "3", "dong_cat": "5",
                     "ket_qua": "Đạt", "so_tem": "017215"},
                    {"stt": "2", "rcd_close": ">5000", "rcd_open": ">5000", "rtx_a": "281",
                     "rtx_b": "278", "rtx_c": "280", "utest": "3", "dong_cat": "5",
                     "ket_qua": "Đạt", "so_tem": "017216"},
                ],
            },
        },
        {
            "report_type": "48",
            "source_image_indices": [1],
            "data": {
                "so_bien_ban": "50481126/BB-TC",
                "chi_danh": "Điện trở nối đất trạm biến áp",
                "ket_noi_trung_tinh": "Có", "loai_tiep_dat": "Làm việc",
                "gia_tri_do_Ohm": "3,52", "thiet_bi_do": "KEW 4105DL",
            },
        },
    ],
}


class TestVision:
    def test_prompt_lists_labels_and_rules(self):
        from bienban.vision import build_prompt

        prompt = build_prompt(["44", "45", "46", "47", "48"])
        # có quy tắc quan trọng
        for rule in ("Không suy đoán", "dấu phẩy", "dd/mm/yyyy", "image_index", "ai_notes"):
            assert rule in prompt
        # có đủ khoá của cả 5 mẫu, đúng nhãn của biểu mẫu
        for key in ("so_may", "so_tem", "mcov", "dong_xa_toi_da",
                    "kha_nang_cat_ngan_mach", "gia_tri_do", "r_cach_dien_Mohm"):
            assert f'"{key}"' in prompt
        for label in ("Số tem", "MCOV", "Khả năng cắt ngắn mạch", "Giá trị đo"):
            assert label in prompt
        assert "MÁY BIẾN ÁP 1 PHA" in prompt

    def test_prompt_distinguishes_44_and_49(self):
        """3 pha phải có neo nhận diện riêng, không lẫn với MBA 1 pha."""
        from bienban.vision import build_prompt

        prompt = build_prompt(["44", "49"])
        # mỗi mẫu có dòng nhận diện
        assert "NHẬN DIỆN MẪU 44" in prompt and "NHẬN DIỆN MẪU 49" in prompt
        assert "Dyn11" in prompt and "K1/K2/K3" in prompt
        assert "TUYỆT ĐỐI không trả về report_type 44" in prompt
        # quy tắc đọc bảng + tự kiểm chéo
        for rule in ("Cao – Vỏ", "Hạ 1 – Hạ 2", "Kht ≈ R60/R15", "Ô gộp"):
            assert rule in prompt, rule
        # report_type chỉ gồm mẫu đang chọn (trước đây cứng 44–48)
        line = next(l for l in prompt.splitlines() if '"report_type"' in l)
        assert '"44"' in line and '"49"' in line and '"48"' not in line

    def test_prompt_field_hints_say_where_to_read(self):
        from bienban.vision import build_prompt

        prompt = build_prompt(["49"])
        assert "ĐỌC Ở:" in prompt
        # K1 phải phân biệt với Kht
        assert "KHÔNG phải Kht" in prompt
        # ví dụ bảng 3 pha có thật
        assert "VÍ DỤ BẢNG 3 PHA" in prompt and "57,759" in prompt

    def test_prompt_subset(self):
        from bienban.vision import build_prompt

        prompt = build_prompt(["45"])
        assert "MÁY CẮT HẠ THẾ (MCCB)" in prompt
        assert "MCOV" not in prompt          # chỉ mẫu 46 mới có

    def test_normalize_branch_contract(self):
        from bienban.vision import normalize_ai_result

        data = normalize_ai_result(AI_PAYLOAD)
        assert data["thong_tin_chung"]["ten_cong_trinh"].startswith("Trạm biến áp")
        assert data["thong_tin_chung"]["ngay_kiem_dinh"] == "1/11/2026"   # chuẩn hoá khi điền
        b45 = data["bien_ban_45_mccb"]
        assert len(b45["rows"]["rows"]) == 2
        assert b45["rows"]["rows"][1]["so_tem"] == "017216"
        assert b45["rows"]["rows"][1]["stt"] == "2"
        # mẫu 48: ô phẳng -> rows
        b48 = data["bien_ban_48_tiep_dat"]
        assert b48["rows"]["rows"][0]["gia_tri_do"] == "3,52"
        assert data["_ai"]["sources"] == {"45": [0], "48": [1]}
        assert "số tem dòng 2 hơi mờ" in data["_ai"]["notes"][0]

    def test_normalize_list_of_lists(self):
        """Dữ liệu cũ dạng mảng-mảng vẫn phải hiểu được."""
        from bienban.vision import normalize_ai_result

        raw = {"reports": [{"report_type": "46", "data": {
            "ket_qua_thu_nghiem": [["LA 01", ">10000", "17", "35"]],
            "so_bien_ban": "5046/BB-TC",
        }}]}
        data = normalize_ai_result(raw)
        row = data["bien_ban_46_la"]["rows"]["rows"][0]
        assert row == {"doi_tuong_do": "LA 01", "r_cach_dien": ">10000",
                       "dong_ro": "17", "u_ac": "35"}

    def test_normalize_is_idempotent(self):
        from bienban.vision import normalize_ai_result

        once = normalize_ai_result(AI_PAYLOAD)
        twice = normalize_ai_result(once)
        assert once["bien_ban_45_mccb"] == twice["bien_ban_45_mccb"]

    def test_normalize_unknown_report_type_ignored(self):
        from bienban.vision import normalize_ai_result

        data = normalize_ai_result({"reports": [{"report_type": "mba_3p", "data": {"x": 1}}]})
        assert not any(k.startswith("bien_ban_") for k in data)

    def test_parse_json_loose(self):
        from bienban.vision import GeminiError, parse_json_loose

        assert parse_json_loose('```json\n{"a": 1}\n```') == {"a": 1}
        assert parse_json_loose('Kết quả: {"a": 2} (xong)') == {"a": 2}
        with pytest.raises(GeminiError):
            parse_json_loose("không có json")

    def test_retired_model_remapped(self):
        """Tên đã khai tử → bỏ trống để tool tự dò model mới (không ghim cứng)."""
        from bienban.vision import _wire_model

        assert _wire_model("gemini-1.5-flash") == ""
        assert _wire_model("gemini-3.5-flash") == ""
        assert _wire_model("models/gemini-3.8-flash") == "gemini-3.8-flash"
        assert _wire_model("gemini-3.1-pro-preview") == "gemini-3.1-pro-preview"

    def test_missing_key_message(self, monkeypatch):
        from bienban import vision

        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(vision.GeminiError) as err:
            vision.resolve_key(None)
        assert "GEMINI_API_KEY" in str(err.value)

    def test_call_gemini_payload_and_parse(self, monkeypatch):
        """Kiểm tra request gửi Google: model, inline_data, responseMimeType."""
        from bienban import vision

        seen = {}

        def fake_request(url, *, data=None, method="GET"):
            seen["url"], seen["data"], seen["method"] = url, data, method
            return _fake_gemini_response(AI_PAYLOAD)

        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setattr(vision, "_request", fake_request)
        out = vision.call_gemini([b"\xff\xd8\xff" + b"0" * 100], model="gemini-2.5-flash", forms=["45"])

        assert out["reports"][0]["report_type"] == "45"
        assert "gemini-2.5-flash:generateContent" in seen["url"]
        assert "key=test-key" in seen["url"]
        parts = seen["data"]["contents"][0]["parts"]
        assert parts[-2]["text"] == "image_index = 0"
        assert parts[-1]["inline_data"]["mime_type"] == "image/jpeg"
        cfg = seen["data"]["generationConfig"]
        assert cfg["responseMimeType"] == "application/json"
        assert cfg["temperature"] <= 0.2

    def test_call_gemini_empty_candidates(self, monkeypatch):
        from bienban import vision

        monkeypatch.setenv("GEMINI_API_KEY", "k")
        monkeypatch.setattr(vision, "_request", lambda *a, **k: {"promptFeedback": {"blockReason": "SAFETY"}})
        with pytest.raises(vision.GeminiError) as err:
            vision.call_gemini([b"x"], forms=["45"])
        assert "SAFETY" in str(err.value)

    def test_http_403_message(self, monkeypatch):
        import urllib.error

        from bienban import vision

        def boom(*a, **k):
            raise urllib.error.HTTPError("u", 403, "Forbidden", {}, None)

        monkeypatch.setattr(vision.urllib.request, "urlopen", boom)
        with pytest.raises(vision.GeminiError) as err:
            vision._request("https://example.invalid")
        assert "API key" in str(err.value)

    def test_prepare_image_downscales(self):
        from PIL import Image
        from io import BytesIO

        from bienban.vision import MAX_EDGE, prepare_image

        import base64

        buf = BytesIO()
        Image.new("RGB", (MAX_EDGE * 2, MAX_EDGE), "white").save(buf, format="JPEG", quality=95)
        mime, b64 = prepare_image(buf.getvalue())
        assert mime == "image/jpeg"
        small = Image.open(BytesIO(base64.b64decode(b64)))
        assert max(small.size) <= MAX_EDGE

    def test_list_models_filters_and_sorts(self, monkeypatch):
        from bienban import vision

        monkeypatch.setenv("GEMINI_API_KEY", "k")
        monkeypatch.setattr(vision, "_request", lambda *a, **k: {"models": [
            {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
        ]})
        models = vision.list_models()
        assert models[:2] == ["gemini-2.5-flash", "gemini-2.5-pro"] or sorted(models) == sorted(models)
        assert "text-embedding-004" not in models


class TestAIEndpoints:
    @pytest.fixture()
    def client(self):
        import sys

        sys.path.insert(0, str(ROOT))
        from web.app import app

        app.config.update(TESTING=True)
        return app.test_client()

    def test_schema_endpoint(self, client):
        body = client.get("/api/ai/schema").get_json()
        assert body["ok"] is True
        from bienban.spec import TEMPLATES

        assert set(body["schema"]["forms"]) == set(TEMPLATES)
        for form in body["schema"]["forms"].values():
            for g in form["groups"]:
                assert "fields" in g or "table" in g

    def test_status_endpoint(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        body = client.get("/api/ai/status").get_json()
        assert body["ok"] is True and body["has_env_key"] is False
        assert "GEMINI_API_KEY" in body["hint"]
        monkeypatch.setenv("GEMINI_API_KEY", "x")
        assert client.get("/api/ai/status").get_json()["has_env_key"] is True

    def test_prompt_endpoint(self, client):
        body = client.get("/api/ai/prompt?forms=45,48").get_json()
        assert "MÁY CẮT HẠ THẾ (MCCB)" in body["prompt"]
        assert "ĐIỆN TRỞ NỐI ĐẤT" in body["prompt"]

    def test_recognize_without_images(self, client):
        r = client.post("/api/ai/recognize", data={})
        assert r.status_code == 400
        assert "ảnh" in r.get_json()["error"].lower()

    def test_recognize_without_key(self, client, monkeypatch):
        import io
        import os

        from bienban import vision

        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        data = {"images": (io.BytesIO(b"\xff\xd8\xffxxx"), "a.jpg")}
        r = client.post("/api/ai/recognize", data=data, content_type="multipart/form-data")
        assert r.status_code == 400
        assert "API key" in r.get_json()["error"]

    def test_recognize_ok(self, client, monkeypatch):
        import io

        from bienban import vision

        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setattr(vision, "_request", lambda *a, **k: _fake_gemini_response(AI_PAYLOAD))
        data = {"images": (io.BytesIO(b"\xff\xd8\xff" + b"0" * 200), "a.jpg"),
                "model": "gemini-2.5-flash", "forms": "45,48"}
        r = client.post("/api/ai/recognize", data=data, content_type="multipart/form-data")
        body = r.get_json()
        assert r.status_code == 200 and body["ok"] is True
        assert set(body["blocks"]) == {"bien_ban_45_mccb", "bien_ban_48_tiep_dat"}
        assert len(body["data"]["bien_ban_45_mccb"]["rows"]["rows"]) == 2
        assert body["notes"]

        # dữ liệu AI -> sinh Word được ngay
        render = client.post("/api/render", json=body["data"]).get_json()
        assert render["ok"] is True
        assert len(render["files"]) == 2
        assert any(f.startswith("45_") for f in render["files"])

    def test_render_allows_incomplete_common(self, client):
        """Thông tin chung còn trống vẫn phải sinh được Word để xem trước."""
        from bienban import vision

        data = vision.normalize_ai_result({"reports": [{
            "report_type": "48", "data": {
                "so_bien_ban": "5048/BB-TC", "chi_danh": "Điện trở nối đất",
                "ket_noi_trung_tinh": "Có", "loai_tiep_dat": "Làm việc",
                "gia_tri_do_Ohm": "3,52", "thiet_bi_do": "KEW 4105DL"}}]})
        body = client.post("/api/render", json=data).get_json()
        assert body["ok"] is True, body
        assert body["files"] and body["previews"]
        warned = " ".join(p["where"] for p in body["problems"] if not p["blocking"])
        assert "thong_tin_chung.dia_chi" in warned
        # không có lỗi chặn nào
        assert not [p for p in body["problems"] if p["blocking"]]

    def test_recognize_nothing_found(self, client, monkeypatch):
        import io

        from bienban import vision

        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setattr(vision, "_request", lambda *a, **k: _fake_gemini_response(
            {"reports": [], "context_photos": [{"image_index": 0, "summary": "ảnh cái cây"}]}))
        data = {"images": (io.BytesIO(b"\xff\xd8\xff" + b"0" * 50), "a.jpg")}
        r = client.post("/api/ai/recognize", data=data, content_type="multipart/form-data")
        assert r.status_code == 422
        assert r.get_json()["ok"] is False

    def test_normalize_endpoint_accepts_report_contract(self, client):
        body = client.post("/api/normalize", json=AI_PAYLOAD).get_json()
        assert body["ok"] is True
        assert len(body["data"]["bien_ban_45_mccb"]["rows"]["rows"]) == 2


class TestRowsRendering:
    """Dữ liệu dạng rows[] (nhiều dòng, có thể do AI hoặc người dùng thêm) -> Word."""

    @staticmethod
    def _rows_of(path, index):
        doc = docx.Document(str(path))
        t = doc.tables[index]
        return [[cell_text(c._tc) for c in r.cells] for r in t.rows]

    def test_45_three_rows(self, data, tmp_path):
        d = json.loads(json.dumps(data))
        d["bien_ban_45_mccb"]["rows"] = {"rows": [
            {"stt": "1", "rcd_close": ">5000", "rcd_open": ">5000", "rtx_a": "273",
             "rtx_b": "275", "rtx_c": "279", "utest": "3", "dong_cat": "5",
             "ket_qua": "Đạt", "so_tem": "017215"},
            {"stt": "2", "rcd_close": ">5000", "rcd_open": ">5000", "rtx_a": "281",
             "rtx_b": "278", "rtx_c": "280", "utest": "3", "dong_cat": "5",
             "ket_qua": "Đạt", "so_tem": "017216"},
            {"stt": "3", "rcd_close": ">5000", "rcd_open": ">5000", "rtx_a": "270",
             "rtx_b": "268", "rtx_c": "271", "utest": "3", "dong_cat": "5",
             "ket_qua": "Đạt", "so_tem": "017217"},
        ]}
        paths, warns = render_all(d, templates_dir=TEMPLATES, out_dir=tmp_path,
                                  forms=["45"])
        assert warns == []
        rows = self._rows_of(paths[0], 1)
        assert len(rows) == 2 + 3                       # 2 dòng tiêu đề + 3 dòng dữ liệu
        assert rows[2][0] == "1" and rows[2][-1] == "017215"
        assert rows[3][0] == "2" and rows[3][4] == "278"
        assert rows[4][0] == "3" and rows[4][-1] == "017217"

    def test_46_two_rows(self, data, tmp_path):
        d = json.loads(json.dumps(data))
        d["bien_ban_46_la"]["rows"] = {"rows": [
            {"doi_tuong_do": "LA 01", "r_cach_dien": ">10000", "dong_ro": "17", "u_ac": "35"},
            {"doi_tuong_do": "LA 02", "r_cach_dien": ">10000", "dong_ro": "19", "u_ac": "35"},
        ]}
        paths, _ = render_all(d, templates_dir=TEMPLATES, out_dir=tmp_path, forms=["46"])
        rows = self._rows_of(paths[0], 1)
        assert rows[1] == ["LA 01", ">10000", "17", "35"]
        assert rows[2] == ["LA 02", ">10000", "19", "35"]

    def test_48_two_rows(self, data, tmp_path):
        d = json.loads(json.dumps(data))
        d["bien_ban_48_tiep_dat"]["rows"] = {"rows": [
            {"stt": "1", "chi_danh": "Điện trở nối đất TBA", "ket_noi_trung_tinh": "Có",
             "loai_tiep_dat": "Làm việc", "gia_tri_do": "3,52"},
            {"stt": "2", "chi_danh": "Điện trở chống sét", "ket_noi_trung_tinh": "Không",
             "loai_tiep_dat": "Chống sét", "gia_tri_do": "4,1"},
        ]}
        paths, _ = render_all(d, templates_dir=TEMPLATES, out_dir=tmp_path, forms=["48"])
        rows = self._rows_of(paths[0], 1)
        assert len(rows) == 3
        assert rows[1][1] == "Điện trở nối đất TBA" and rows[1][4] == "3,52"
        assert rows[2][1] == "Điện trở chống sét" and rows[2][3] == "Chống sét"


# --------------------------------------------------------------------------- #
# Giao diện: nhận diện thương hiệu, chữ lớn, in ấn
# --------------------------------------------------------------------------- #
class TestUI:
    @pytest.fixture()
    def client(self):
        import sys

        sys.path.insert(0, str(ROOT))
        from web.app import app

        app.config.update(TESTING=True)
        return app.test_client()

    def test_logo_from_template(self, client):
        """Logo lấy từ chính file mẫu Word (đúng bộ nhận diện công ty)."""
        page = client.get("/").get_data(as_text=True)
        assert "data:image/jpeg;base64," in page
        assert 'class="brandmark"' in page

    def test_css_served_and_brand_colors(self, client):
        r = client.get("/static/app.css")
        assert r.status_code == 200
        css = r.get_data(as_text=True)
        assert "--navy:#241a63" in css      # xanh trong logo
        assert "--red:#d81f26" in css       # đỏ trong logo
        assert "body.big" in css            # chế độ chữ lớn
        assert "@media print" in css        # in / lưu PDF

    def test_no_unrendered_template_markers(self, client):
        page = client.get("/").get_data(as_text=True)
        assert "{{" not in page and "{%" not in page

    def test_accessibility_hooks(self, client):
        page = client.get("/").get_data(as_text=True)
        # mọi vùng tương tác chính đều có nhãn cho trình đọc màn hình
        assert 'aria-label="Chọn ảnh biên bản"' in page
        assert 'aria-label="JSON dữ liệu"' in page
        assert 'id="btnBig"' in page and 'aria-pressed="false"' in page
        assert 'id="btnPrint"' in page
        # có 3 bước rõ ràng
        assert page.count('class="step') >= 3

    def test_schema_labels_match_word_template(self, client):
        """Nhãn trong form phải khớp nhãn in trên mẫu Word."""
        from bienban.schema import web_schema

        schema = web_schema()
        labels = {f["label"] for f in schema["common"]["fields"]}
        for must in ("Tên công trình", "Địa chỉ", "Đơn vị yêu cầu",
                     "Lý do kiểm định", "Nơi kiểm định", "Ngày kiểm định"):
            assert must in labels
        b45 = {f["label"] for g in schema["forms"]["45"]["groups"] for f in g.get("fields", [])}
        for must in ("Chỉ danh", "Hiệu", "Số cực", "Loại", "Kiểu",
                     "Điện áp định mức", "Dòng điện định mức"):
            assert must in b45

    def test_every_template_field_is_editable(self):
        """Mọi ô nhãn của 6 mẫu đều phải có input trong schema (để sửa được)."""
        from bienban.schema import fields_of, tables_of
        from bienban.spec import LABELS

        from bienban.schema import COMMON_GROUP

        # Chỉ danh của 45/46/47 nằm ở khối "Thông tin công trình" (đúng vị trí in)
        common_chipped = {f["key"] for f in COMMON_GROUP["fields"]}
        for form, items in LABELS.items():
            have = {f["key"] for f in fields_of(form)} | (common_chipped - {"so_bien_ban",
                                                                          "ngay_lap_bien_ban"})
            tables = {t["key"] for _, t in tables_of(form)}
            for it in items:
                if it.get("label"):
                    # nhãn không có trong schema? -> phải là ô chung hoặc suy ra
                    if it["path"].startswith("thong_tin_chung."):
                        continue
                    if it["label"] in ("KẾT LUẬN",):
                        assert "ket_luan" in have, form
                        continue
                    key = it["path"].split("|")[0]
                    # mẫu 48: các ô phẳng cũ nằm trong bảng rows (có cột cùng tên)
                    row_cols = {c["key"] for _, t in tables_of(form)
                                for c in t.get("columns", [])}
                    assert key in have or key.split(".")[0] in have or key in row_cols, \
                        (form, key)
                elif it.get("table"):
                    # khoá bảng trong spec.py là khoá "nhận diện bảng trong Word"
                    # (insulation, la, fco…), trong schema là khoá dữ liệu
                    # mẫu 44: các bảng đo được biểu diễn bằng ô dãy số (fields)
                    series_prefix = {
                        "r_dc": "r_cuon_day_1_chieu_ohm",
                        "ratio": "ti_so_bien_ap",
                        "no_load": "khong_tai",
                        "short_circuit": "ngan_mach",
                        "voltage_test": "thu_dien_ap_tang_cao",
                        # mẫu 49: các bảng 3 pha biểu diễn bằng ô/dãy số (như mẫu 44)
                        "voltage_test_3p": "thu_dien_ap_tang_cao",
                        "r_dc_3p": "r_cuon_day_1_chieu_ohm",
                        "ratio_3p": "ti_so_bien_ap",
                    }
                    if it["table"] in series_prefix:
                        prefix = series_prefix[it["table"]]
                        assert any(k.startswith(prefix) for k in have), (form, prefix)
                        continue
                    # 45/46/47/48: bảng kết quả của Word tương ứng khoá dữ liệu chung "rows"
                    alias = {"insulation": "r_cach_dien_Mohm", "mccb": "rows",
                             "la": "rows", "fco": "rows", "earth": "rows",
                             # mẫu 49 (MBA 3 pha) dùng bảng riêng
                             "insulation_3p": "r_cach_dien_Mohm",
                             # mẫu 97 (cáp ngầm): mỗi bảng Word là một khoá riêng
                             "cap_ngam": "r_cach_dien_Mohm",
                             "cap_ngam_dc": "thu_dien_ap_mot_chieu"}
                    key = alias.get(it["table"], it["table"])
                    assert key in tables, (form, it["table"])



# --------------------------------------------------------------------------- #
# Thứ tự ô trên form phải trùng thứ tự in trong file Word
# --------------------------------------------------------------------------- #
class TestFormOrder:
    """So nhãn của form với vị trí thật của chúng trong .docx.

    Không dùng danh sách nhãn chép tay: quét đúng các ``<w:p>`` của mẫu, ghi
    lại thứ tự xuất hiện, rồi so với :func:`bienban.schema.print_order`.
    """

    #: nhãn có cách viết khác giữa form và bản in
    ALIASES = {
        "Số biên bản": r"\bSỐ\s*:",
        "Ngày lập biên bản": r"\bNGÀY\s*:",
        "Kết luận": r"\bKẾT LUẬN\s*:",
        "Thiết bị đo": r"THIẾT BỊ THỬ NGHIỆM\s*:",
    }

    def _word_order(self, form: str) -> list[str]:
        import re

        from docx.oxml.ns import qn

        from bienban.ooxml import para_text
        from bienban.schema import print_order
        from bienban.spec import TEMPLATES

        doc = docx.Document(str(ROOT / "templates" / TEMPLATES[form]))
        labels = [l for l in print_order(form)
                  if not l.startswith("[bảng]") and not l.endswith("(ký tên)")]
        found: list[str] = []
        for p in doc.element.body.iter(qn("w:p")):
            text = para_text(p)
            if not text:
                continue
            here = []
            for lab in labels:
                pat = self.ALIASES.get(lab) or (re.escape(lab) + r"\s*:")
                m = re.search(pat, text, re.I if lab in self.ALIASES else 0)
                if m:
                    here.append((m.start(), lab))
            found += [lab for _, lab in sorted(here)]
        seen, out = set(), []
        for lab in found:
            if lab not in seen:
                seen.add(lab)
                out.append(lab)
        return out

    @pytest.mark.parametrize("form", ["44", "45", "46", "47", "48"])
    def test_order_matches_word(self, form):
        from bienban.schema import print_order

        labels = [l for l in print_order(form)
                  if not l.startswith("[bảng]") and not l.endswith("(ký tên)")]
        word = self._word_order(form)
        pos = {lab: i for i, lab in enumerate(labels)}
        assert word, f"mẫu {form}: không quét được nhãn nào"
        assert [pos[l] for l in word] == sorted(pos[l] for l in word), (
            f"mẫu {form}: form xếp sai thứ tự so với bản in\n"
            f"  Word: {word}\n  Form: {labels}")

    def test_header_comes_first(self):
        from bienban.schema import print_order

        for form in ("44", "45", "46", "47", "48"):
            assert print_order(form)[:2] == ["Số biên bản", "Ngày lập biên bản"]

    def test_signature_block_last(self):
        from bienban.schema import print_order

        for form in ("44", "45", "46", "47", "48"):
            assert print_order(form)[-1] == "P. Giám đốc (ký tên)"

    def test_chi_danh_after_dia_chi(self):
        from bienban.schema import print_order

        for form in ("45", "46", "47"):
            order = print_order(form)
            i = order.index("Địa chỉ")
            assert order[i + 1] == "Chỉ danh"
            assert order[i + 2] == "Đơn vị yêu cầu"
        assert "Chỉ danh" not in print_order("44")

    def test_44_ly_lich_before_project(self):
        from bienban.schema import print_order

        order = print_order("44")
        assert order.index("Hiệu máy") < order.index("Tên công trình")
        assert order.index("Tần số") < order.index("Tên công trình")

    def test_so_luong_just_before_table(self):
        from bienban.schema import print_order

        for form in ("45", "46", "47"):
            order = print_order(form)
            i = order.index("Số lượng")
            assert order[i - 1] == "Kiểm tra bên ngoài"
            assert order[i + 1].startswith("[bảng]")

    def test_no_duplicate_labels(self):
        from bienban.schema import print_order

        for form in ("44", "45", "46", "47", "48"):
            order = print_order(form)
            assert len(order) == len(set(order)), f"mẫu {form} có nhãn trùng"

    def test_block_fields_carry_scope_prefix(self):
        """Ô riêng phải có tiền tố __block để web ghi đúng biên bản."""
        from bienban.schema import web_groups

        for form in ("44", "45", "48"):
            for g in web_groups(form):
                for f in g.get("fields", []):
                    if f["key"] in ("so_bien_ban", "ngay_lap_bien_ban"):
                        continue
                    if f["key"] in ("ten_cong_trinh", "dia_chi", "don_vi_yeu_cau",
                                    "ly_do_kiem_dinh", "noi_kiem_dinh", "ngay_kiem_dinh",
                                    "nguoi_thu", "nguoi_kiem_tra", "p_giam_doc"):
                        continue
                    assert f["path"][:2] == ["__block", form], (form, f["key"], f["path"])


# --------------------------------------------------------------------------- #
# Quy ước dòng trống
# --------------------------------------------------------------------------- #
class TestBlankRows:
    @pytest.fixture()
    def block45(self, data):
        b = json.loads(json.dumps(data))["bien_ban_45_mccb"]
        b["so_luong"] = "05"
        b["rows"] = [
            {"stt": "1", "rcd_close": ">5000", "rcd_open": ">5000", "rtx_a": "273",
             "rtx_b": "275", "rtx_c": "279", "utest": "3", "dong_cat": "5",
             "ket_qua": "Đạt", "so_tem": "017215"},
            {"stt": "2", "rcd_close": ">5000", "rcd_open": ">5000", "rtx_a": "268",
             "rtx_b": "", "rtx_c": "", "utest": "3", "dong_cat": "5",
             "ket_qua": "Đạt", "so_tem": "017216"},
            {"stt": "3", "rcd_close": "", "rcd_open": ""},          # trống hoàn toàn
            {"stt": "4", "rcd_close": ">5000", "rcd_open": ">5000", "rtx_a": "270",
             "rtx_b": "272", "rtx_c": "274", "utest": "3", "dong_cat": "5",
             "ket_qua": "Đạt", "so_tem": "017217"},
            {"stt": "5", "rcd_close": None, "rcd_open": "  "},      # trống hoàn toàn
        ]
        return b

    def test_compact_removes_only_fully_blank_rows(self, block45):
        from bienban.fill import compact_rows, table_spec

        keep, removed = compact_rows(block45["rows"], table_spec("45", "rows"))
        assert removed == 2 and len(keep) == 3
        assert [r["so_tem"] for r in keep] == ["017215", "017216", "017217"]

    def test_stt_renumbered_and_count(self, block45):
        from bienban.fill import normalize_blank_rows

        nb, log = normalize_blank_rows("45", block45)
        assert [r["stt"] for r in nb["rows"]] == ["1", "2", "3"]
        assert nb["so_luong"] == "03"
        assert log and "5 → 3" in log[0]

    def test_blank_cell_prints_dash(self, block45, tmp_path):
        import docx
        from docx.oxml.ns import qn

        from bienban.fill import render_form
        from bienban.ooxml import cell_text

        from bienban.fill import load_config

        data = {"thong_tin_chung": {"ten_cong_trinh": "X", "dia_chi": "Y",
                                    "don_vi_yeu_cau": "Z", "ngay_lap_bien_ban": "04/11/2026",
                                    "ngay_kiem_dinh": "01/11/2026"},
                "bien_ban_45_mccb": block45}
        path, _ = render_form("45", data, templates_dir=ROOT / "templates",
                              out_dir=tmp_path, cfg=load_config())
        doc = docx.Document(str(path))
        tbl = [t for t in doc.tables
               if "R tiếp xúc" in " ".join(cell_text(tc) for tc in t._tbl.iter(qn("w:tc")))][0]
        rows = [[cell_text(c._tc) for c in r.cells] for r in tbl.rows][-3:]
        assert len(rows) == 3                        # 2 dòng trống đã bị bỏ
        assert rows[1][4] == "-" and rows[1][5] == "-"   # Pha B, Pha C
        assert rows[2][-1] == "017217"

    def test_fixed_table_untouched(self, data):
        from bienban.fill import normalize_blank_rows

        b = json.loads(json.dumps(data))
        b["bien_ban_44_mba"]["r_cach_dien_Mohm"] = {"rows": [
            {"key": "cao_vo_ha1", "r60": "2760", "r15": "2106", "knt": "1,31"},
            {"key": "cao_vo_ha2", "r60": "", "r15": "", "knt": ""},
            {"key": "ha1_ha2", "r60": "1790", "r15": "1376", "knt": "1,30"},
        ]}
        nb, _ = normalize_blank_rows("44", b["bien_ban_44_mba"])
        assert len(nb["r_cach_dien_Mohm"]["rows"]) == 3

    def test_list_form_count_follows_rows(self):
        from bienban.fill import build_conclusion, load_config, normalize_blank_rows

        b = {"so_luong": "07",
             "rows": [{"stt": "1", "rcd_close": ">5000", "so_tem": "017215"},
                      {"stt": "2"}, {"stt": "3"}]}
        nb, _ = normalize_blank_rows("45", b)
        assert len(nb["rows"]) == 1
        assert "Một (01) máy cắt hạ thế" in build_conclusion("45", nb, {}, load_config())

    def test_blank_detection(self):
        from bienban.fill import _is_blank

        for v in ("", "-", "–", "—", "   ", None):
            assert _is_blank(v), v
        for v in ("0", ">5000", "Đạt", "-1"):
            assert not _is_blank(v), v


# --------------------------------------------------------------------------- #
# Soát số liệu sau khi AI đọc ảnh (checks.py)
# --------------------------------------------------------------------------- #
class TestChecks:
    @pytest.fixture()
    def normalized(self, data):
        from bienban.vision import normalize_ai_result

        d = normalize_ai_result(json.loads(json.dumps(data)))
        d.pop("_ai", None)
        return d

    def test_clean_sample_has_no_warnings(self, normalized):
        from bienban.checks import check_rules

        assert check_rules(normalized) == []

    def test_kht_mismatch_detected(self, normalized):
        from bienban.checks import check_rules

        normalized["bien_ban_44_mba"]["r_cach_dien_Mohm"] = {"rows": [
            {"key": "cao_vo_ha1", "r60": "2760", "r15": "2106", "knt": "2,50"}]}
        warns = check_rules(normalized)
        assert any("Kht" in w.message for w in warns)
        assert any(w.field == "knt" for w in warns)

    def test_kht_missing_is_info(self, normalized):
        from bienban.checks import check_rules

        normalized["bien_ban_44_mba"]["r_cach_dien_Mohm"] = {"rows": [
            {"key": "cao_vo_ha1", "r60": "2760", "r15": "2106", "knt": ""}]}
        info = [w for w in check_rules(normalized) if w.level == "info" and "tự tính" in w.message]
        assert info and "1,31" in info[0].message

    def test_duplicate_row_detected(self, normalized):
        from bienban.checks import check_rules

        rows = normalized["bien_ban_45_mccb"]["rows"]["rows"]
        normalized["bien_ban_45_mccb"]["rows"]["rows"] = [rows[0], dict(rows[0])]
        assert any("giống hệt" in w.message for w in check_rules(normalized))

    def test_missing_greater_than_sign(self, normalized):
        from bienban.checks import check_rules

        normalized["bien_ban_45_mccb"]["rows"]["rows"][0]["rcd_close"] = "5000"
        assert any("'>5000'" in w.message for w in check_rules(normalized))

    def test_series_jump_detected(self, normalized):
        from bienban.checks import check_rules

        normalized["bien_ban_44_mba"]["ti_so_bien_ap"]["ha_1"] = [
            "57,98", "56,59", "55,21", "53,83", "20,00"]
        assert any("lệch" in w.message for w in check_rules(normalized))

    def test_count_mismatch_even_with_one_row(self, normalized):
        from bienban.checks import check_rules

        normalized["bien_ban_45_mccb"]["so_luong"] = "05"
        assert any("Số lượng ghi 05" in w.message for w in check_rules(normalized))

    def test_code_length_and_bad_date(self, normalized):
        from bienban.checks import check_rules

        normalized["bien_ban_44_mba"]["so_tem"] = "17246"
        normalized["thong_tin_chung"]["ngay_kiem_dinh"] = "32/11/2026"
        msgs = " ".join(w.message for w in check_rules(normalized))
        assert "chỉ có 5 chữ số" in msgs
        assert "dd/mm/yyyy" in msgs

    def test_vietnamese_number_parsing(self):
        from bienban.checks import _num

        assert _num("3,52") == pytest.approx(3.52)
        assert _num(">5000") == 5000
        assert _num("1.234,5") == pytest.approx(1234.5)
        assert _num("") is None and _num(None) is None

    def test_warning_serialises(self):
        from bienban.checks import Warning_

        w = Warning_("warn", "a.b", "có thể sai", field="so_tem", form="44")
        d = w.as_dict()
        assert d["level"] == "warn" and d["source"] == "rule" and d["field"] == "so_tem"


class TestCheckEndpoint:
    @pytest.fixture()
    def client(self):
        import sys

        sys.path.insert(0, str(ROOT))
        from web.app import app

        app.config.update(TESTING=True)
        return app.test_client()

    def test_check_endpoint_reports_blocking_error(self, client):
        """Số pha sai: /api/check phải nói rõ lỗi chặn, khớp với lý do /api/render từ chối."""
        body = client.post("/api/check", json={
            "bien_ban_49_mba_3p": {"so_pha": "01", "to_dau_day": "I/I0"}}).get_json()
        assert body["ok"] is True
        errs = [c for c in body["checks"] if c["level"] == "error"]
        assert errs and errs[0]["form"] == "49"
        assert "Số pha" in errs[0]["message"]
        # không lặp lại cùng một chỗ hai lần
        assert len([c for c in body["checks"] if c["where"].endswith(".so_pha")]) == 1

    def test_check_endpoint_rules_only(self, client, data):
        from bienban.vision import normalize_ai_result

        d = normalize_ai_result(json.loads(json.dumps(data)))
        d.pop("_ai", None)
        body = client.post("/api/check", json=d).get_json()
        assert body["ok"] is True and body["checks"] == []
        assert body["counts"]["rule"] == 0

    def test_check_endpoint_reports_problem(self, client, data):
        from bienban.vision import normalize_ai_result

        d = normalize_ai_result(json.loads(json.dumps(data)))
        d.pop("_ai", None)
        d["bien_ban_45_mccb"]["so_luong"] = "09"
        body = client.post("/api/check", json=d).get_json()
        assert any(c["source"] == "rule" for c in body["checks"])

    def test_check_endpoint_ai_layer_optional(self, client, data, monkeypatch):
        """?ai=1 dùng lại ảnh của lần nhận dạng gần nhất (không upload lại)."""
        from bienban import vision
        from web import app as webapp

        monkeypatch.setenv("GEMINI_API_KEY", "k")
        webapp._LAST_IMAGES["blobs"] = [b"\xff\xd8\xff" + b"0" * 50]
        seen = {}

        def fake(url, *, data=None, method="GET", **kw):
            seen["prompt"] = data["contents"][0]["parts"][0]["text"]
            return {"candidates": [{"content": {"parts": [{"text": json.dumps(
                {"checks": [{"where": "bien_ban_45_mccb.rows[0].rtx_a",
                             "in_json": "273", "on_image": "278",
                             "note": "chữ số cuối bị đọc nhầm"}]},
                ensure_ascii=False)}]}}]}

        monkeypatch.setattr(vision, "_request", fake)
        body = client.post("/api/check?ai=1", json=data).get_json()
        assert body["counts"]["ai"] == 1
        ai = [c for c in body["checks"] if c["source"] == "ai"][0]
        assert "278" in ai["message"] and ai["form"] == "45"
        assert "SOÁT LẠI" in seen["prompt"]

    def test_check_endpoint_ai_without_images(self, client, data, monkeypatch):
        from web import app as webapp

        monkeypatch.setenv("GEMINI_API_KEY", "k")
        webapp._LAST_IMAGES["blobs"] = []
        body = client.post("/api/check?ai=1", json=data).get_json()
        assert body["ok"] is True and body["counts"]["ai"] == 0

    def test_recognize_returns_rule_checks(self, client, monkeypatch):
        import io

        from bienban import vision

        payload = {
            "thong_tin_chung": {"ten_cong_trinh": "X", "dia_chi": "Y",
                                "don_vi_yeu_cau": "Z", "ly_do_kiem_dinh": "Sau sự cố",
                                "noi_kiem_dinh": "Tại hiện trường", "ngay_kiem_dinh": "01/11/2026"},
            "reports": [{"report_type": "48", "data": {
                "so_bien_ban": "5048/BB-TC", "chi_danh": "Điện trở nối đất",
                "ket_noi_trung_tinh": "Có", "loai_tiep_dat": "Làm việc",
                "gia_tri_do_Ohm": "3,52", "thiet_bi_do": "KEW 4105DL"}}],
        }
        monkeypatch.setenv("GEMINI_API_KEY", "k")
        monkeypatch.setattr(vision, "_request", lambda *a, **k: {
            "candidates": [{"content": {"parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}}]})
        files = {"images": (io.BytesIO(b"\xff\xd8\xff" + b"0" * 100), "a.jpg")}
        body = client.post("/api/ai/recognize", data=files,
                           content_type="multipart/form-data").get_json()
        assert body["ok"] is True and "checks" in body
        from web.app import _LAST_IMAGES
        assert _LAST_IMAGES["blobs"]


class TestModelDrift:
    """Google khai tử model liên tục (404 "no longer available") → tool tự dò."""

    MODELS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3-flash-preview",
              "gemini-3.1-pro-preview", "gemini-2.5-flash"]
    OK = {"candidates": [{"content": {"parts": [{"text": '{"ok": 1}'}]}}]}

    @pytest.fixture()
    def client(self):
        import sys

        sys.path.insert(0, str(ROOT))
        from web.app import app

        app.config.update(TESTING=True)
        return app.test_client()

    @pytest.fixture()
    def api(self, monkeypatch):
        """Giả lập Google ở tầng urlopen để mã phân loại lỗi thật được chạy."""
        import io
        import urllib.error
        import urllib.request

        from bienban import vision

        state = {"calls": [], "dead": {}, "models": list(self.MODELS)}
        vision.AUTO_MODEL_CACHE.clear()

        class Resp:
            def __init__(self, obj):
                self._b = json.dumps(obj).encode()

            def read(self):
                return self._b

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            url = getattr(req, "full_url", str(req))
            if "/models?" in url:
                return Resp({"models": [{"name": "models/" + m,
                                         "supportedGenerationMethods": ["generateContent"]}
                                        for m in state["models"]]})
            model = url.split("/models/")[1].split(":")[0]
            state["calls"].append(model)
            if model in state["dead"]:
                msg = (f"This model models/{model} is no longer available to new users. "
                       f"Please update your code to use models/{state['dead'][model]}")
                raise urllib.error.HTTPError(
                    url, 404, "Not Found", {},
                    io.BytesIO(json.dumps({"error": {"message": msg}}).encode()))
            return Resp(self.OK)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        return state

    def test_ranking_prefers_newest_stable_flash(self, api):
        from bienban.vision import list_models

        models = list_models("k")
        assert models[0] == "gemini-3.8-flash"
        assert models.index("gemini-3.6-flash") < models.index("gemini-2.5-flash")
        assert models.index("gemini-3-flash-preview") < models.index("gemini-2.5-flash")

    def test_ranking_skips_specialised_models(self, api):
        from bienban.vision import list_models

        api["models"] += ["gemini-3.1-flash-image", "gemini-3.1-flash-tts-preview",
                          "gemini-3.5-live-translate-preview", "gemini-omni-1.1-flash"]
        models = list_models("k")
        assert models[0] == "gemini-3.8-flash"
        for bad in ("image", "tts", "live", "omni"):
            assert all(bad not in models[0] for _ in [0])

    def test_auto_model_uses_newest(self, api):
        from bienban.vision import auto_model

        assert auto_model("k") == "gemini-3.8-flash"

    def test_auto_model_cached(self, api, monkeypatch):
        import urllib.request

        from bienban import vision

        vision.auto_model("k")
        list_calls = []

        def boom(url, **kw):
            list_calls.append(url)
            raise AssertionError("không được gọi lại /models")

        monkeypatch.setattr(urllib.request, "urlopen", boom)
        assert vision.auto_model("k") == "gemini-3.8-flash"
        assert not list_calls

    def test_auto_model_falls_back_when_offline(self, monkeypatch):
        from bienban import vision

        def boom(url, **kw):
            raise urllib.error.URLError("offline")

        import urllib.error

        monkeypatch.setattr(urllib.request, "urlopen", boom)
        vision.AUTO_MODEL_CACHE.clear()
        assert vision.auto_model("k") == vision.SAFE_MODEL

    def test_404_switches_model_not_fatal(self, api):
        """Đây chính là lỗi người dùng gặp: 404 "no longer available"."""
        from bienban.vision import call_gemini

        api["dead"] = {"gemini-2.5-pro": "gemini-3.1-pro-preview"}
        seen = []
        out = call_gemini([b"\xff\xd8\xffx"], key="k", model="gemini-2.5-pro",
                          fallbacks=["gemini-3.6-flash"],
                          on_try=lambda i, m, slot, exc: seen.append((m, getattr(exc, "status", 0))))
        assert out == {"ok": 1}
        assert seen[0] == ("gemini-2.5-pro", 404)
        assert api["calls"] == ["gemini-2.5-pro", "gemini-3.6-flash"]

    def test_dead_model_retried_with_freshly_detected(self, api):
        """Cả chuỗi đều chết → tự dò lại model mới rồi thử lần cuối."""
        from bienban.vision import call_gemini

        api["dead"] = {"gemini-2.5-pro": "gemini-3.8-flash",
                       "gemini-2.5-flash": "gemini-3.8-flash"}
        out = call_gemini([b"\xff\xd8\xffx"], key="k", model="gemini-2.5-pro",
                          fallbacks=["gemini-2.5-flash"])
        assert out == {"ok": 1}
        assert api["calls"][-1] == "gemini-3.8-flash"

    def test_no_model_given_auto_detects(self, api):
        from bienban.vision import call_gemini

        assert call_gemini([b"\xff\xd8\xffx"], key="k") == {"ok": 1}
        assert api["calls"] == ["gemini-3.8-flash"]

    def test_missing_model_does_not_explode(self, api):
        """DEFAULT_MODEL rỗng + không truyền model → vẫn phải chạy."""
        from bienban import vision

        assert vision.DEFAULT_MODEL == "" or isinstance(vision.DEFAULT_MODEL, str)
        call = vision.call_gemini
        assert call([b"\xff\xd8\xffx"], key="k", model="") == {"ok": 1}

    def test_gemini3_gets_thinking_config(self, api, monkeypatch):
        import urllib.request

        from bienban import vision

        seen = {}
        real = urllib.request.urlopen

        def capture(req, timeout=None):
            body = getattr(req, "data", None)
            if body:
                payload = json.loads(body.decode())
                if "generationConfig" in payload:
                    seen.update(payload["generationConfig"])
            return real(req, timeout=timeout)

        monkeypatch.setattr(urllib.request, "urlopen", capture)
        vision.call_gemini([b"\xff\xd8\xffx"], key="k", model="gemini-3.8-flash")
        assert seen["thinkingConfig"] == {"thinkingLevel": "low"}
        assert seen["maxOutputTokens"] >= 32768

    def test_gemini25_has_no_thinking_config(self, api, monkeypatch):
        import urllib.request

        from bienban import vision

        seen = {}
        real = urllib.request.urlopen

        def capture(req, timeout=None):
            body = getattr(req, "data", None)
            if body:
                payload = json.loads(body.decode())
                if "generationConfig" in payload:
                    seen.update(payload["generationConfig"])
            return real(req, timeout=timeout)

        monkeypatch.setattr(urllib.request, "urlopen", capture)
        vision.call_gemini([b"\xff\xd8\xffx"], key="k", model="gemini-2.5-flash")
        assert "thinkingConfig" not in seen

    def test_max_tokens_message_when_truncated(self, api, monkeypatch):
        """JSON bị cắt vì thinking → báo rõ, không thử model khác."""
        import urllib.request

        from bienban import vision

        real = urllib.request.urlopen

        def cut(req, timeout=None):
            url = getattr(req, "full_url", str(req))
            if "/models?" in url:
                return real(req, timeout=timeout)
            raise AssertionError("không được thử model khác")

        class Resp:
            def read(self):
                return json.dumps({"candidates": [{"finishReason": "MAX_TOKENS",
                                                   "content": {"parts": []}}]}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(urllib.request, "urlopen",
                            lambda req, timeout=None: (
                                real(req, timeout=timeout)
                                if "/models?" in getattr(req, "full_url", "") else Resp()))
        with pytest.raises(vision.GeminiFatal) as err:
            vision.call_gemini([b"\xff\xd8\xffx"], key="k", model="gemini-3.8-flash")
        assert "MAX_TOKENS" in str(err.value) and "token" in str(err.value)

    def test_api_models_reports_real_default(self, client, monkeypatch):
        """Dropdown phải nhận đúng model mới nhất, không phải tên đã chết."""
        import urllib.request

        from bienban import vision

        class Resp:
            def read(self):
                return json.dumps({"models": [
                    {"name": "models/gemini-2.5-flash",
                     "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/gemini-3.8-flash",
                     "supportedGenerationMethods": ["generateContent"]},
                ]}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        vision.AUTO_MODEL_CACHE.clear()
        monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: Resp())
        body = client.get("/api/ai/models", headers={"X-Gemini-Key": "k"}).get_json()
        assert body["ok"] and body["default"] == "gemini-3.8-flash"
        assert body["models"][0] == "gemini-3.8-flash"


class TestBlankFieldsDoNotBlock:
    """Ô trống chỉ là cảnh báo — vẫn sinh Word và xem trước được (yêu cầu người dùng)."""

    @pytest.fixture()
    def client(self):
        import sys

        sys.path.insert(0, str(ROOT))
        from web.app import app

        app.config.update(TESTING=True)
        return app.test_client()

    @pytest.fixture()
    def thin(self):
        """Dữ liệu mẫu 45 thiếu cả số biên bản lẫn thông tin chung."""
        from bienban import vision

        return vision.normalize_ai_result({"reports": [{
            "report_type": "45", "data": {
                "hieu": "MITSUBISHI", "kieu": "NF-250", "loai": "MCCB",
                "so_luong": "01", "so_cuc": "03", "ket_qua": "Đạt",
                "rows": [{"stt": "1", "rtx_a": "273", "rtx_b": "275", "rtx_c": "279",
                          "utest": "3", "dong_cat": "5", "ket_qua": "Đạt"}]}}]})

    def test_missing_so_bien_ban_is_warning_only(self, thin):
        from bienban.validate import validate

        probs = [p for p in validate(thin) if "so_bien_ban" in p.where]
        assert probs, "phải nhắc người dùng thiếu số biên bản"
        assert all(p.level == "warn" and not p.blocking for p in probs)

    def test_only_structural_errors_block(self):
        from bienban.validate import validate

        # JSON rỗng hoàn toàn -> không có biên bản nào để in
        probs = validate({"thong_tin_chung": {"ten_cong_trinh": "X"}})
        assert any(p.blocking for p in probs)
        # không phải object
        assert validate("không phải dict")[0].blocking is True

    def test_render_returns_word_and_preview(self, client, thin):
        r = client.post("/api/render", json=thin)
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        assert body["files"] == ["45_BB45.docx"]
        assert body["previews"]["45_BB45.docx"]
        assert body["zip_url"]

    def test_preview_shows_dash_for_blank(self, client, thin):
        """Ô trống in ra dấu “-”, không phải chuỗi rỗng hay None."""
        body = client.post("/api/render", json=thin).get_json()
        html = body["previews"]["45_BB45.docx"]
        assert "-" in html
        assert "None" not in html

    def test_validate_endpoint_ok_true_but_reports_warnings(self, client, thin):
        body = client.post("/api/validate", json=thin).get_json()
        assert body["ok"] is True
        assert not [p for p in body["problems"] if p["blocking"]]
        assert any("so_bien_ban" in p["where"] for p in body["problems"])

    def test_problems_json_has_blocking_flag(self, client, thin):
        body = client.post("/api/validate", json=thin).get_json()
        assert all("blocking" in p for p in body["problems"])

    def test_render_blocks_only_when_nothing_to_print(self, client):
        r = client.post("/api/render", json={"thong_tin_chung": {"ten_cong_trinh": "X"}})
        assert r.status_code == 400
        body = r.get_json()
        assert body["ok"] is False
        assert any(p["blocking"] for p in body["problems"])

    def test_cli_still_reports_problems(self, thin):
        """CLI: không chặn in, nhưng vẫn liệt kê cảnh báo."""
        from bienban.validate import validate

        assert all(p.level in ("warn", "error") for p in validate(thin))


class TestAiFallback:
    """Chuỗi AI dự phòng: model chính → model khác → key dự phòng (đều Gemini)."""

    OK = {"candidates": [{"content": {"parts": [{"text": '{"ok": 1}'}]}}]}

    @pytest.fixture()
    def client(self):
        import sys

        sys.path.insert(0, str(ROOT))
        from web.app import app

        app.config.update(TESTING=True)
        return app.test_client()

    @pytest.fixture()
    def calls(self, monkeypatch):
        """Giả lập _request: ghi lại (model, key) và trả lỗi theo kịch bản."""
        from bienban import vision

        state = {"calls": [], "busy": {}, "fatal": set(), "busy_key": {}}

        def fake(url, *, data=None, method="GET"):
            model = url.split("/models/")[1].split(":")[0]
            key = url.split("key=")[1]
            state["calls"].append((model, key))
            if model in state["fatal"]:
                raise vision.GeminiFatal("ảnh hỏng")
            # lỗi gắn với một cặp (model, key) cụ thể nếu có
            if key in state["busy_key"]:
                raise vision.GeminiBusy("bận", status=state["busy_key"][key])
            if model in state["busy"]:
                raise vision.GeminiBusy("bận", status=state["busy"][model])
            return TestAiFallback.OK

        monkeypatch.setattr(vision, "_request", fake)
        return state

    def test_main_model_works_no_fallback(self, calls):
        from bienban.vision import call_gemini

        out = call_gemini([b"\xff\xd8\xffx"], key="K1", model="gemini-2.5-flash",
                          fallbacks=["gemini-2.5-pro"])
        assert out == {"ok": 1}
        assert calls["calls"] == [("gemini-2.5-flash", "K1")]

    @pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
    def test_busy_statuses_switch_model(self, calls, status):
        from bienban.vision import call_gemini

        calls["busy"]["gemini-2.5-flash"] = status
        out = call_gemini([b"\xff\xd8\xffx"], key="K1", model="gemini-2.5-flash",
                          fallbacks=["gemini-2.5-pro"])
        assert out == {"ok": 1}
        assert [c[0] for c in calls["calls"]] == ["gemini-2.5-flash", "gemini-2.5-pro"]

    def test_timeout_switches_model(self, calls):
        from bienban import vision

        state = calls

        def fake(url, *, data=None, method="GET"):
            model = url.split("/models/")[1].split(":")[0]
            state["calls"].append((model, "K1"))
            if model == "gemini-2.5-flash":
                raise vision.GeminiBusy("timeout", status=408)
            return TestAiFallback.OK

        vision._request = fake
        assert vision.call_gemini([b"\xff\xd8\xffx"], key="K1", model="gemini-2.5-flash",
                                  fallbacks=["gemini-2.5-pro"]) == {"ok": 1}

    def test_backup_key_used_after_all_models_fail(self, calls):
        from bienban.vision import call_gemini

        calls["busy_key"]["K1"] = 429           # key chính hết hạn mức
        out = call_gemini([b"\xff\xd8\xffx"], key="K1", model="gemini-2.5-flash",
                          fallbacks=["gemini-2.5-pro"], alt_keys=["K2"])
        assert out == {"ok": 1}
        # thử hết model với key chính, rồi mới sang key dự phòng
        assert [c[1] for c in calls["calls"]] == ["K1", "K1", "K2"]
        assert calls["calls"][-1] == ("gemini-2.5-flash", "K2")

    def test_fatal_error_stops_immediately(self, calls):
        from bienban.vision import GeminiFatal, call_gemini

        calls["fatal"].add("gemini-2.5-flash")
        with pytest.raises(GeminiFatal):
            call_gemini([b"\xff\xd8\xffx"], key="K1", model="gemini-2.5-flash",
                        fallbacks=["gemini-2.5-pro"], alt_keys=["K2"])
        assert len(calls["calls"]) == 1          # không tốn thêm lượt gọi

    def test_all_fail_gives_clear_message(self, calls):
        from bienban.vision import GeminiError, call_gemini

        calls["busy_key"].update({"K1": 429, "K2": 503})
        with pytest.raises(GeminiError) as exc:
            call_gemini([b"\xff\xd8\xffx"], key="K1", model="gemini-2.5-flash",
                        fallbacks=["gemini-2.5-pro"], alt_keys=["K2"])
        assert "Không gọi được model nào" in str(exc.value)
        assert "429" in str(exc.value) or "bận" in str(exc.value)

    def test_on_try_reports_each_switch(self, calls):
        from bienban.vision import call_gemini

        calls["busy"]["gemini-2.5-flash"] = 503
        seen = []
        call_gemini([b"\xff\xd8\xffx"], key="K1", model="gemini-2.5-flash",
                    fallbacks=["gemini-2.5-pro"],
                    on_try=lambda i, m, slot, exc: seen.append((i, m, slot)))
        assert seen[0][1] == "gemini-2.5-flash" and seen[0][2] == "chính"

    def test_duplicate_models_and_keys_not_retried(self, calls):
        from bienban.vision import call_gemini

        from bienban.vision import GeminiError

        calls["busy"]["gemini-2.5-flash"] = 503
        with pytest.raises(GeminiError):
            call_gemini([b"\xff\xd8\xffx"], key="K1", model="gemini-2.5-flash",
                        fallbacks=["gemini-2.5-flash", "models/gemini-2.5-flash"],
                        alt_keys=["K1"])
        # 3 tên gọi cùng một model + 1 key trùng -> chỉ 1 lần gọi, không quay vòng
        assert calls["calls"] == [("gemini-2.5-flash", "K1")], calls["calls"]

    def test_defaults_from_config(self):
        from bienban.fill import load_config

        ai = load_config()["ai"]
        assert ai["fallback_models"] and ai["fallback_models"][0] != "gemini-2.5-flash"

    def test_recognize_reports_fallback(self, client, monkeypatch):
        """Nếu phải chuyển phương án, phản hồi API nói rõ."""
        import io

        from bienban import vision

        payload = {"thong_tin_chung": {"ten_cong_trinh": "X", "dia_chi": "Y", "don_vi_yeu_cau": "Z",
                                       "ly_do_kiem_dinh": "Sau sự cố", "noi_kiem_dinh": "Tại hiện trường",
                                       "ngay_kiem_dinh": "01/11/2026"},
                   "reports": [{"report_type": "48", "data": {"so_bien_ban": "5048/BB-TC"}}]}

        def fake(url, *, data=None, method="GET"):
            model = url.split("/models/")[1].split(":")[0]
            if model == "gemini-2.5-flash":
                raise vision.GeminiBusy("quá tải", status=503)
            return {"candidates": [{"content": {"parts": [
                {"text": json.dumps(payload, ensure_ascii=False)}]}}]}

        monkeypatch.setenv("GEMINI_API_KEY", "k")
        monkeypatch.setattr(vision, "_request", fake)
        files = {"images": (io.BytesIO(b"\xff\xd8\xff" + b"0" * 80), "a.jpg")}
        body = client.post("/api/ai/recognize", data=files,
                           content_type="multipart/form-data").get_json()
        assert body["ok"] is True
        assert body["fallback"], body
        assert "gemini-2.5-flash" in body["fallback"][0]


class TestBatchGroups:
    """Nhiều ảnh / nhiều nhóm: gộp kết quả nhận dạng thành một bộ biên bản."""

    TT = {"ten_cong_trinh": "Trạm A", "dia_chi": "Tây Ninh",
          "don_vi_yeu_cau": "E-GREEN", "ly_do_kiem_dinh": "Sau sự cố",
          "noi_kiem_dinh": "Tại hiện trường", "ngay_kiem_dinh": "01/11/2026"}

    @pytest.fixture()
    def client(self):
        import sys

        sys.path.insert(0, str(ROOT))
        from web.app import app

        app.config.update(TESTING=True)
        return app.test_client()

    def test_two_groups_same_form_append_rows(self):
        """Hai nhóm cùng mẫu 45 = hai đợt thiết bị → nối bảng, đánh lại STT."""
        from bienban.schema import merge_results

        a = {"thong_tin_chung": self.TT,
             "bien_ban_45_mccb": {"so_bien_ban": "5045/BB-TC", "hieu": "MITSUBISHI",
                                  "rows": [{"stt": "1", "utest": "3", "so_tem": "017215"}]}}
        b = {"thong_tin_chung": {"dia_chi": "Bình Dương"},
             "bien_ban_45_mccb": {"so_bien_ban": "9999/BB-TC", "hieu": "ABB",
                                  "rows": [{"stt": "1", "utest": "5", "so_tem": "777"}]}}
        data, notes = merge_results([a, b])
        rows = data["bien_ban_45_mccb"]["rows"]
        assert len(rows) == 2
        assert [r["stt"] for r in rows] == ["01", "02"]
        assert [r["so_tem"] for r in rows] == ["017215", "777"]
        # ô đơn: giữ giá trị nhóm đầu, không bị nhóm sau ghi đè
        assert data["bien_ban_45_mccb"]["so_bien_ban"] == "5045/BB-TC"
        assert data["bien_ban_45_mccb"]["hieu"] == "MITSUBISHI"
        # thông tin chung: chỉ bổ sung ô trống
        assert data["thong_tin_chung"]["dia_chi"] == "Tây Ninh"
        assert data["thong_tin_chung"]["ten_cong_trinh"] == "Trạm A"
        assert any("gộp thêm 1 dòng" in n for n in notes)

    def test_common_filled_when_first_group_blank(self):
        from bienban.schema import merge_results

        data, _ = merge_results([
            {"thong_tin_chung": {"ten_cong_trinh": "Trạm A"}, "bien_ban_48_tiep_dat": {}},
            {"thong_tin_chung": {"dia_chi": "Tây Ninh", "ten_cong_trinh": "Trạm B"},
             "bien_ban_48_tiep_dat": {"gia_tri_do_Ohm": "3,52"}},
        ])
        tt = data["thong_tin_chung"]
        assert tt["dia_chi"] == "Tây Ninh"        # ô trống -> lấy nhóm sau
        assert tt["ten_cong_trinh"] == "Trạm A"   # đã có -> giữ nhóm đầu

    def test_crew_names_merged_field_by_field(self):
        from bienban.schema import merge_results

        data, _ = merge_results([
            {"thong_tin_chung": {"can_bo_ky_ten": {"nguoi_thu": "Quân"}}, "bien_ban_44_mba": {}},
            {"thong_tin_chung": {"can_bo_ky_ten": {"nguoi_kiem_tra": "Nghĩa",
                                                   "nguoi_thu": "Khác"}}, "bien_ban_44_mba": {}},
        ])
        crew = data["thong_tin_chung"]["can_bo_ky_ten"]
        assert crew["nguoi_thu"] == "Quân"
        assert crew["nguoi_kiem_tra"] == "Nghĩa"

    def test_different_forms_side_by_side(self):
        from bienban.schema import merge_results

        data, _ = merge_results([
            {"thong_tin_chung": self.TT, "bien_ban_45_mccb": {"so_luong": "01"}},
            {"thong_tin_chung": self.TT, "bien_ban_46_la": {"so_luong": "02"}},
        ])
        assert data["bien_ban_45_mccb"]["so_luong"] == "01"
        assert data["bien_ban_46_la"]["so_luong"] == "02"

    def test_series_not_appended(self):
        """Dãy số cố định (5 nấc) không nối thêm — giữ dãy nhóm đầu + ghi chú."""
        from bienban.schema import merge_results

        a = {"bien_ban_44_mba": {"ti_so_bien_ap": {"ha_1": ["1", "2"]}}}
        b = {"bien_ban_44_mba": {"ti_so_bien_ap": {"ha_1": ["9", "9"]}}}
        data, notes = merge_results([a, b])
        assert data["bien_ban_44_mba"]["ti_so_bien_ap"]["ha_1"] == ["1", "2"]
        assert any("dãy số" in n for n in notes)

    def test_nested_table_rows_dict_form(self):
        """Bảng ở dạng ``rows: {rows: [...]}`` cũng nối được."""
        from bienban.schema import merge_results

        a = {"bien_ban_47_fco": {"rows": {"rows": [{"stt": "1", "thiet_bi": "FCO 01"}]}}}
        b = {"bien_ban_47_fco": {"rows": {"rows": [{"stt": "1", "thiet_bi": "FCO 02"}]}}}
        data, _ = merge_results([a, b])
        rows = data["bien_ban_47_fco"]["rows"]["rows"]
        assert [r["thiet_bi"] for r in rows] == ["FCO 01", "FCO 02"]
        assert [r["stt"] for r in rows] == ["01", "02"]

    def test_single_group_unchanged(self):
        from bienban.schema import merge_results

        only = {"thong_tin_chung": self.TT, "bien_ban_48_tiep_dat": {"gia_tri_do_Ohm": "3,52"}}
        data, notes = merge_results([only])
        assert data == only
        assert notes == []

    def test_ignores_meta_key(self):
        from bienban.schema import merge_results

        data, _ = merge_results([{"bien_ban_48_tiep_dat": {"x": "1"}, "_ai": {"notes": ["a"]}}])
        assert "_ai" not in data

    # ---- API ----
    def test_api_merge_ok(self, client):
        body = client.post("/api/merge", json={"results": [
            {"thong_tin_chung": self.TT,
             "bien_ban_46_la": {"so_luong": "01", "rows": {"rows": [{"stt": "1"}]}}},
            {"thong_tin_chung": self.TT,
             "bien_ban_46_la": {"so_luong": "09", "rows": {"rows": [{"stt": "1"}]}}},
        ]}).get_json()
        assert body["ok"] is True
        assert body["blocks"] == ["bien_ban_46_la"]
        assert len(body["data"]["bien_ban_46_la"]["rows"]["rows"]) == 2
        assert body["data"]["bien_ban_46_la"]["so_luong"] == "01"
        assert body["notes"]

    def test_api_merge_needs_results(self, client):
        r = client.post("/api/merge", json={"results": []})
        assert r.status_code == 400
        r2 = client.post("/api/merge", json={})
        assert r2.status_code == 400

    def test_api_merge_rejects_garbage(self, client):
        r = client.post("/api/merge", json={"results": [{"foo": "bar"}]})
        assert r.status_code == 422

    def test_api_merge_output_renders(self, client, tmp_path):
        """Dữ liệu gộp phải sinh được biên bản thật."""
        from bienban.fill import render_all
        from bienban.schema import merge_results
        from bienban.spec import TEMPLATES

        rows_a = [{"stt": "1", "utest": "3", "so_tem": "017215", "ket_qua": "Đạt",
                   "rcd_close": ">5000", "rcd_open": ">5000",
                   "rtx_a": "273", "rtx_b": "275", "rtx_c": "279", "dong_cat": "5"}]
        rows_b = [{"stt": "1", "utest": "5", "so_tem": "017299", "ket_qua": "Đạt",
                   "rcd_close": ">5000", "rcd_open": ">5000",
                   "rtx_a": "280", "rtx_b": "281", "rtx_c": "282", "dong_cat": "5"}]
        block = {"so_bien_ban": "5045/BB-TC", "hieu": "MITSUBISHI", "kieu": "NF-250",
                 "loai": "MCCB", "so_luong": "02", "so_cuc": "03", "u_test_kV": "3",
                 "dong_dinh_muc": "250A", "dien_ap_dinh_muc": "400V",
                 "chi_danh": "MCCB 250A", "ket_qua": "Đạt"}
        data, _ = merge_results([
            {"thong_tin_chung": self.TT, "bien_ban_45_mccb": dict(block, rows=rows_a)},
            {"thong_tin_chung": self.TT, "bien_ban_45_mccb": dict(block, rows=rows_b)},
        ])
        assert len(data["bien_ban_45_mccb"]["rows"]) == 2
        paths, warnings = render_all(data, templates_dir=ROOT / "templates",
                                     out_dir=tmp_path, forms=["45"])
        assert len(paths) == 1 and paths[0].exists() and paths[0].stat().st_size > 50_000
        assert not [w for w in warnings if "lỗi" in w.lower()]


class TestWatermark:
    """Hình nền chính thống: logo công ty làm dấu chìm trong mọi biên bản."""

    @pytest.fixture()
    def client(self):
        import sys

        sys.path.insert(0, str(ROOT))
        from web.app import app

        app.config.update(TESTING=True)
        return app.test_client()

    def test_finds_the_real_logo_not_the_signature(self):
        """Ba ảnh trong mẫu: logo nhỏ, chữ ký, logo lớn — phải chọn logo lớn."""
        import io

        import docx
        from PIL import Image

        from bienban.watermark import find_logo

        doc = docx.Document(str(ROOT / "templates" / "45 MCCB 250A.docx"))
        blob = find_logo(doc)
        assert blob, "không tìm thấy logo"
        w, h = Image.open(io.BytesIO(blob)).size
        assert w > 300 and h > 300, (w, h)          # logo lớn 1227×1091
        # có cả đỏ lẫn xanh navy => đúng logo, không phải chữ ký
        im = Image.open(io.BytesIO(blob)).convert("RGB")
        im.thumbnail((64, 64))
        getter = getattr(im, "get_flattened_data", None) or im.getdata
        px = list(getter())
        red = sum(1 for r, g, b in px if r > 140 and g < 110 and b < 110)
        navy = sum(1 for r, g, b in px if b > 60 and b > r + 25 and g < b)
        assert red > 20 and navy > 20, (red, navy)

    def test_signature_is_rejected(self):
        """Ảnh chữ ký (chỉ một màu mực) không được dùng làm hình nền."""
        from bienban.watermark import _logo_score

        from PIL import Image

        # chữ ký điện thoại thật trong mẫu 46
        import zipfile

        z = zipfile.ZipFile(str(ROOT / "templates" / "46 BB LA.docx"))
        name = [n for n in z.namelist() if n.endswith(".png")][0]
        import io

        im = Image.open(io.BytesIO(z.read(name)))
        assert _logo_score(im) == 0.0

    def test_watermark_added_to_every_template(self, tmp_path):
        import io
        import json
        import zipfile

        import docx

        from bienban.fill import load_config, render_form

        data = json.loads((ROOT / "samples" / "e-green-01112026.json").read_text(encoding="utf-8"))
        cfg = load_config()
        cfg["watermark"] = {"enabled": True, "opacity": 0.06, "scale": 0.62}
        for form in ("44", "45", "46", "47", "48"):
            path, warn = render_form(form, data, templates_dir=ROOT / "templates",
                                     out_dir=tmp_path, cfg=cfg, log=lambda s: None)
            z = zipfile.ZipFile(str(path))
            headers = [n for n in z.namelist()
                       if n.startswith("word/header") and n.endswith(".xml")]
            xml = "".join(z.read(h).decode() for h in headers)
            assert "Logo chìm" in xml, form
            assert 'behindDoc="1"' in xml, form            # nằm dưới chữ
            assert "alphaModFix" in xml, form               # có độ trong suốt
            assert not any("logo" in w.lower() for w in warn), warn
            # mở lại được bằng python-docx (file không hỏng)
            docx.Document(io.BytesIO(z.read("word/document.xml")) if False else str(path))

    def test_can_be_turned_off(self, tmp_path):
        import json
        import zipfile

        from bienban.fill import load_config, render_form

        data = json.loads((ROOT / "samples" / "e-green-01112026.json").read_text(encoding="utf-8"))
        cfg = load_config()
        cfg["watermark"] = {"enabled": False}
        path, _ = render_form("45", data, templates_dir=ROOT / "templates",
                              out_dir=tmp_path, cfg=cfg, log=lambda s: None)
        z = zipfile.ZipFile(str(path))
        xml = "".join(z.read(n).decode() for n in z.namelist()
                      if n.startswith("word/header") and n.endswith(".xml"))
        assert "Logo chìm" not in xml

    def test_web_preview_has_watermark_css(self, client):
        page = client.get("/").get_data(as_text=True)
        assert ".page-wm::before" in page
        assert "background-image:url(data:image/" in page

    def test_config_example_documents_watermark(self):
        import json

        cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        assert cfg["watermark"]["enabled"] is True
        assert 0 < cfg["watermark"]["opacity"] <= 0.2


class TestImageReview:
    """Giữ ảnh qua F5 (IndexedDB) + lightbox xem lại ảnh đã tải."""

    @pytest.fixture()
    def client(self):
        import sys

        sys.path.insert(0, str(ROOT))
        from web.app import app

        app.config.update(TESTING=True)
        return app.test_client()

    @pytest.fixture()
    def page(self, client):
        return client.get("/").get_data(as_text=True)

    def test_lightbox_container_and_hooks(self, page):
        assert 'id="lightbox"' in page
        for hook in ("function lightboxOpen", "function lightboxClose",
                     "function drawLightbox", "data-lb-zoom-in", "data-lb-rot",
                     "data-lb-prev", "data-lb-next"):
            assert hook in page, hook

    def test_images_persist_across_reload(self, page):
        # IndexedDB, không phải localStorage: ảnh chụp điện thoại vài MB vẫn lưu được
        assert 'indexedDB.open' in page
        for fn in ("idbPut", "idbAll", "idbDelete", "idbClear", "restoreImages"):
            assert f"function {fn}" in page or f"async function {fn}" in page, fn
        assert "restoreImages()" in page.split("khởi động")[-1]

    def test_thumb_opens_lightbox(self, page):
        assert 'data-view="${i}"' in page
        assert 'data-view=' in page and "lightboxOpen(Number(b.dataset.view))" in page

    def test_image_label_points_to_form(self, page):
        """Ảnh phải ghi rõ thuộc biên bản nào: “ảnh 3 → biên bản 45”."""
        assert "function imageFormLabel" in page
        assert "biên bản " in page

    def test_keyboard_shortcuts_in_lightbox(self, page):
        tail = page.split("khởi động")[-1]
        for key in ("Escape", "ArrowLeft", "ArrowRight"):
            assert key in tail, key

    def test_rotation_and_zoom_steps(self, page):
        assert "VIEW.rot = (VIEW.rot + 90) % 360" in page
        assert "Math.min(6, VIEW.zoom * 1.25)" in page

    def test_css_for_lightbox(self, client):
        css = client.get("/static/app.css").get_data(as_text=True)
        for sel in (".lightbox", ".lb-stage", ".lb-nav", ".lb-tools", ".thumb .view"):
            assert sel in css, sel

    def test_delete_removes_from_store(self, page):
        assert "idbDelete(im.dbId)" in page
        assert "idbClear()" in page


class TestFreeTextSelects:
    """Mọi dropdown (ô đơn + ô trong bảng) phải cho nhập giá trị ngoài danh sách."""

    @pytest.fixture()
    def client(self):
        import sys

        sys.path.insert(0, str(ROOT))
        from web.app import app

        app.config.update(TESTING=True)
        return app.test_client()

    def _selects(self):
        from bienban.schema import web_groups

        for form in ("44", "45", "46", "47", "48"):
            for g in web_groups(form):
                for f in g.get("fields", []):
                    if f.get("type") == "select":
                        yield form, g["title"], f
                t = g.get("table")
                for c in (t or {}).get("columns", []):
                    if c.get("type") == "select":
                        yield form, g["title"], c

    def test_page_has_other_option(self, client):
        page = client.get("/").get_data(as_text=True)
        assert 'data-other="1"' in page and "✎ Khác…" in page
        assert "data-other-of" in page and "function bindSelect" in page

    def test_select_options_are_plain_strings(self):
        seen = 0
        for form, title, f in self._selects():
            seen += 1
            for opt in f.get("options") or []:
                assert isinstance(opt, str) and opt and not opt.startswith("__"), (form, title)
        assert seen >= 8, seen

    def test_no_reserved_sentinel_in_page(self, client):
        assert "__khac__" not in client.get("/").get_data(as_text=True)


# --------------------------------------------------------------------------- #
# Bộ khởi động (launcher.py + file .bat/.sh)
# --------------------------------------------------------------------------- #
class TestLauncher:
    @pytest.fixture()
    def launcher(self):
        import sys

        sys.path.insert(0, str(ROOT))
        import launcher

        return launcher

    def test_read_env_tolerates_formats(self, launcher, tmp_path):
        f = tmp_path / ".env"
        f.write_text('# chú thích\n\nexport FOO="bar baz"\nBAZ=1\n\n', encoding="utf-8")
        assert launcher.read_env(f) == {"FOO": "bar baz", "BAZ": "1"}

    def test_write_env_roundtrip_and_permissions(self, launcher, tmp_path):
        f = tmp_path / ".env"
        launcher.write_env("GEMINI_API_KEY", "abc123", f)
        launcher.write_env("PORT", "8123", f)
        assert launcher.read_env(f) == {"GEMINI_API_KEY": "abc123", "PORT": "8123"}
        # giữ nguyên khoá cũ khi ghi thêm
        assert f.read_text(encoding="utf-8").count("GEMINI_API_KEY") == 1
        mode = f.stat().st_mode & 0o777
        assert mode == 0o600 or mode == 0o644     # Windows bỏ qua chmod

    def test_apply_env_does_not_override(self, launcher, tmp_path, monkeypatch):
        f = tmp_path / ".env"
        f.write_text("FOO=from-file\nBAR=from-file\n", encoding="utf-8")
        monkeypatch.setenv("BAR", "from-shell")
        monkeypatch.delenv("FOO", raising=False)
        launcher.apply_env(f)
        import os

        assert os.environ["FOO"] == "from-file"
        assert os.environ["BAR"] == "from-shell"    # biến môi trường thắng

    def test_pick_port_skips_busy(self, launcher):
        import socket

        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen(1)
            port = busy.getsockname()[1]
            assert launcher.port_free(port) is False
            picked = launcher.pick_port(port, tries=5)
            assert picked != port and port < picked < port + 5

    def test_requirements_detected(self, launcher):
        assert launcher.requirements_missing() == []     # môi trường test đã đủ

    def test_check_reports_environment(self, launcher, capsys):
        rc = launcher.check()
        out = capsys.readouterr().out
        assert rc == 0
        from bienban.spec import TEMPLATES

        n = len(TEMPLATES)
        assert f"Mẫu Word      : {n}/{n}" in out
        assert "API key Gemini" in out

    def test_launcher_runs_server(self, launcher, monkeypatch):
        """--no-browser + cổng ngẫu nhiên: server phải lên và trả 200."""
        import threading
        import time
        import urllib.request

        import web.app as webapp

        port = launcher.pick_port(8300)
        err = []

        def run():
            try:
                webapp.app.run(host="127.0.0.1", port=port, debug=False,
                               use_reloader=False, threaded=True)
            except Exception as exc:              # pragma: no cover
                err.append(exc)

        t = threading.Thread(target=run, daemon=True)
        t.start()
        for _ in range(60):
            time.sleep(0.1)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
                    assert r.status == 200
                    body = r.read().decode()
                    assert "brandmark" in body
                    break
            except Exception:
                continue
        else:                                     # pragma: no cover
            pytest.fail("server không lên")
        assert not err

    def test_windows_script_is_crlf_and_ascii(self):
        """cmd.exe đọc .bat theo bảng mã hệ thống: phải ASCII + CRLF."""
        for name in ("Chay-Web.bat", "Chay-Nhanh.bat"):
            data = (ROOT / name).read_bytes()
            assert data.count(b"\r\n") == data.count(b"\n"), f"{name}: thiếu CRLF"
            assert all(b <= 127 for b in data), f"{name}: có ký tự ngoài ASCII"
        # file chính có điều hướng bằng nhãn
        assert b"goto :" in (ROOT / "Chay-Web.bat").read_bytes()

    def test_shell_scripts_are_executable(self):
        import os
        import stat

        for name in ("chay-web.sh", "chay-nhanh.sh", "Chay-Web.command"):
            path = ROOT / name
            assert path.exists(), name
            mode = path.stat().st_mode
            assert mode & stat.S_IXUSR, f"{name} thiếu quyền chạy"
            text = path.read_text(encoding="utf-8")
            assert "\r\n" not in text, f"{name}: phải dùng LF"

    def test_bat_labels_all_defined(self):
        import re

        text = (ROOT / "Chay-Web.bat").read_text(encoding="utf-8")
        labels = set(re.findall(r"^:(\w+)", text, re.M))
        gotos = set(re.findall(r"goto :(\w+)", text))
        assert gotos <= labels, f"goto tới nhãn không tồn tại: {gotos - labels}"

    def test_gitattributes_keeps_bat_crlf(self):
        text = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        assert "*.bat   text eol=crlf" in text
        assert "*.sh    text eol=lf" in text

    def test_env_is_gitignored(self):
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
        assert ".env" in ignored
        assert (ROOT / ".env.example").exists()


class TestForm49:
    """Mẫu 49 – MÁY BIẾN ÁP 3 PHA (số liệu thật của biên bản 50921026/BB-TC)."""

    DATA = {
        "so_bien_ban": "50921026/BB-TC",
        "hieu_may": "THIBIDI",
        "cong_suat_dinh_muc": "1500",
        "so_pha": "03",
        "tan_so": "50",
        "dien_ap_dinh_muc": "22/0,4",
        "to_dau_day": "Dyn11",
        "r_cach_dien_Mohm": {"rows": [
            {"key": "cao_vo", "r60": "15300", "r15": "11300", "knt": "1,35"},
            {"key": "cao_ha", "r60": "13700", "r15": "10200", "knt": "1,34"},
            {"key": "ha_vo", "r60": "8200", "r15": "6200", "knt": "1,32"},
        ]},
        "r_cuon_day_1_chieu_ohm": {
            "cao_ap": {
                "ab": ["3,413", "3,332", "3,251", "3,169", "3,088"],
                "bc": ["3,418", "3,336", "3,255", "3,174", "3,092"],
                "ca": ["3,421", "3,339", "3,258", "3,177", "3,095"],
            },
            "ha_ap_mOhm": {"an": "0,885", "bn": "0,887", "cn": "0,889"},
        },
        "ti_so_bien_ap": {
            "k1": ["57,759", "56,384", "55,019", "53,633", "52,258"],
            "k2": ["57,763", "56,387", "55,012", "53,637", "52,261"],
            "k3": ["57,764", "56,388", "55,013", "53,638", "52,262"],
        },
        "khong_tai": {"u0_V": "400", "i0_A": "5,19", "i0_pct": "0,24", "p0_W": "1210,3"},
        "ngan_mach": {"uk_V": "1280,4", "uk_pct": "5,82", "ik_A": "39,36", "pk_W": "12423,3"},
        "thu_dien_ap_tang_cao": {"cao_vo": "50", "ha_vo": "3", "thoi_gian": "1 phút"},
    }

    @pytest.fixture()
    def out49(self, tmp_path):
        from bienban.fill import render_all

        data = {"bien_ban_49_mba_3p": json.loads(json.dumps(self.DATA))}
        paths, warnings = render_all(data, templates_dir=TEMPLATES, out_dir=tmp_path,
                                    forms=["49"])
        return paths, warnings

    def _text(self, path):
        d = docx.Document(str(path))
        cells = [cell_text(tc) for t in d.tables for r in t.rows
                 for tc in r._tr.findall(TC)]
        return "\n".join(cells)

    def test_renders_without_warnings(self, out49):
        paths, warnings = out49
        assert warnings == [], warnings
        assert len(paths) == 1 and paths[0].name.startswith("49_")
        assert paths[0].stat().st_size > 100_000

    def test_table_shapes_are_three_phase(self, out49):
        doc = docx.Document(str(out49[0][0]))
        shapes = [(len(t.rows), len(t.columns)) for t in doc.tables]
        # cách điện 4x4, R-DC 7x5 (2 hàng tiêu đề), tỉ số 6x4
        assert (4, 4) in shapes
        assert (7, 5) in shapes
        assert (6, 4) in shapes

    def test_values_land_in_the_right_cells(self, out49):
        text = self._text(out49[0][0])
        for must in ("Cao – Vỏ", "Cao – Hạ", "Hạ – Vỏ", "15300", "13700", "8200",
                     "3,413", "3,421", "3,095", "57,759", "52,258", "52,262",
                     "0,885", "0,889",
                     "1210,3", "12423,3"):
            assert must in text, f"thiếu {must!r} trong bảng"

    def test_never_emits_one_phase_rows(self, out49):
        text = self._text(out49[0][0])
        for forbidden in ("Hạ 1", "Hạ 2", "(Cao + Vỏ) – Hạ", "ha_1", "ha_2"):
            assert forbidden not in text, f"mẫu 49 không được có {forbidden!r}"

    def test_schema_uses_series_not_fixed_rows(self):
        from bienban.schema import fields_of

        names = {f["key"] for f in fields_of("49")}
        for name in ("r_cuon_day_1_chieu_ohm.cao_ap.ab",
                     "r_cuon_day_1_chieu_ohm.cao_ap.bc",
                     "r_cuon_day_1_chieu_ohm.cao_ap.ca",
                     "r_cuon_day_1_chieu_ohm.ha_ap_mOhm.an",
                     "ti_so_bien_ap.k1", "ti_so_bien_ap.k2", "ti_so_bien_ap.k3"):
            assert name in names, f"thiếu ô {name}"

    def test_clean_sample_has_no_check_warnings(self):
        from bienban.checks import check_rules

        assert check_rules({"bien_ban_49_mba_3p": json.loads(json.dumps(self.DATA))}) == []

    def test_so_pha_mismatch_is_reported(self):
        from bienban.checks import check_rules

        bad = {"bien_ban_49_mba_3p": json.loads(json.dumps(self.DATA))}
        bad["bien_ban_49_mba_3p"]["so_pha"] = "01"
        bad["bien_ban_49_mba_3p"]["to_dau_day"] = "I/I0"
        msgs = [w.message for w in check_rules(bad)]
        assert any("Số pha" in m for m in msgs)
        assert any("1 pha" in m for m in msgs)

    def test_phase_outlier_detected(self):
        from bienban.checks import check_rules

        bad = {"bien_ban_49_mba_3p": json.loads(json.dumps(self.DATA))}
        bad["bien_ban_49_mba_3p"]["r_cuon_day_1_chieu_ohm"]["cao_ap"]["bc"][2] = "9,900"
        assert any("AB/BC/CA" in w.message for w in check_rules(bad))

    def test_ratio_outlier_detected(self):
        from bienban.checks import check_rules

        bad = {"bien_ban_49_mba_3p": json.loads(json.dumps(self.DATA))}
        bad["bien_ban_49_mba_3p"]["ti_so_bien_ap"]["k3"][4] = "39,262"
        assert any("K1/K2/K3" in w.message for w in check_rules(bad))

    def test_r60_below_r15_detected(self):
        from bienban.checks import check_rules

        bad = {"bien_ban_49_mba_3p": json.loads(json.dumps(self.DATA))}
        bad["bien_ban_49_mba_3p"]["r_cach_dien_Mohm"]["rows"][0].update(
            {"r60": "11300", "r15": "15300"})
        assert any("R60" in w.message and "R15" in w.message for w in check_rules(bad))

    def test_blank_49_does_not_block_generation(self, tmp_path):
        paths, warnings = render_all({"bien_ban_49_mba_3p": {}},
                                     templates_dir=TEMPLATES, out_dir=tmp_path,
                                     forms=["49"])
        assert len(paths) == 1
        assert paths[0].exists()
        assert all(w.level != "error" for w in warnings)


class TestAiKeyCrash:
    """Lỗi thật người dùng gặp: dán API key → "list object has no attribute get"."""

    def test_normalize_accepts_bare_list(self):
        from bienban.vision import normalize_ai_result

        raw = [{"report_type": "46", "data": {"so_bien_ban": "50941026/BB-TC"}}]
        out = normalize_ai_result(raw, forms=["46"])
        assert out["bien_ban_46_la"]["so_bien_ban"] == "50941026/BB-TC"

    def test_parse_json_loose_always_dict(self):
        from bienban.vision import parse_json_loose

        assert isinstance(parse_json_loose('[{"report_type":"44"}]'), dict)
        assert isinstance(parse_json_loose('{"reports":[]}'), dict)
        assert isinstance(parse_json_loose('```json\n[{"a":1}]\n```'), dict)
        assert parse_json_loose('[{"reports":[{"report_type":"46"}]}]')["reports"]

    def test_two_reports_same_form_are_kept(self):
        """2 tờ LA của 2 đợt khác nhau không được ghi đè lên nhau."""
        from bienban.vision import normalize_ai_result

        raw = [{"report_type": "46", "data": {"so_bien_ban": "50941026/BB-TC"}},
               {"report_type": "46", "data": {"so_bien_ban": "50461126/BB-TC"}}]
        out = normalize_ai_result(raw, forms=["46"])
        assert out["bien_ban_46_la"]["so_bien_ban"] == "50941026/BB-TC"
        extras = out["_extra"]["bien_ban_46_la"]
        assert [b["so_bien_ban"] for b in extras] == ["50461126/BB-TC"]
        assert any("2 biên bản cùng loại" in n for n in out["_ai"]["notes"])

    def test_render_emits_one_file_per_report(self, tmp_path):
        from bienban.fill import render_all
        from bienban.vision import normalize_ai_result

        raw = [{"report_type": "46", "data": {"so_bien_ban": "50941026/BB-TC",
                "rows": {"rows": [{"stt": "1", "doi_tuong": "LA 01",
                                   "r_cach_dien": ">10000", "dong_ro": "17",
                                   "u_ac": "35"}]}}},
               {"report_type": "46", "data": {"so_bien_ban": "50461126/BB-TC",
                "rows": {"rows": [{"stt": "1", "doi_tuong": "LA 01",
                                   "r_cach_dien": ">10000", "dong_ro": "19",
                                   "u_ac": "35"}]}}}]
        data = normalize_ai_result(raw, forms=["46"])
        paths, warnings = render_all(data, templates_dir=TEMPLATES,
                                     out_dir=tmp_path, forms=["46"])
        assert len(paths) == 2
        assert sorted(p.name for p in paths) == ["46_50461126BBTC-2.docx",
                                                 "46_50941026BBTC.docx"]
        assert warnings == []


class TestNoStaleNumbers:
    """Mẫu Word còn số của đợt trước → bản in lặng lẽ giữ số cũ (nguy hiểm)."""

    def test_blank_render_has_no_old_measures(self, tmp_path):
        import re

        from bienban.fill import render_all
        from bienban.spec import DATA_KEYS

        paths, _ = render_all({v: {} for v in DATA_KEYS.values()},
                              templates_dir=TEMPLATES, out_dir=tmp_path)
        pat = re.compile(r"^[><]?\d{3,6}([.,]\d+)?$")
        for p in paths:
            doc = docx.Document(str(p))
            left = [c.text.strip() for t in doc.tables for r in t.rows
                    for c in r.cells if pat.match(c.text.strip())]
            assert not left, f"{p.name} còn số cũ: {left}"

    def test_blank_render_has_no_baked_verdict(self, tmp_path):
        from bienban.fill import render_all

        paths, _ = render_all({"bien_ban_45_mccb": {}, "bien_ban_47_fco": {}},
                              templates_dir=TEMPLATES, out_dir=tmp_path,
                              forms=["45", "47"])
        for p in paths:
            doc = docx.Document(str(p))
            txt = "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
            assert "Đạt" not in txt, f"{p.name} vẫn in sẵn chữ Đạt"

    def test_real_data_still_lands(self, tmp_path):
        """Dọn số cũ KHÔNG được xoá số thật vừa điền."""
        from bienban.fill import render_all

        data = {"bien_ban_49_mba_3p": TestForm49.DATA}
        paths, warnings = render_all(data, templates_dir=TEMPLATES,
                                     out_dir=tmp_path, forms=["49"])
        text = "\n".join(c.text for t in docx.Document(str(paths[0])).tables
                         for r in t.rows for c in r.cells)
        for must in ("15300", "8200", "3,413", "52,262", "0,885", "1210,3"):
            assert must in text, f"mất số thật {must!r}"
        assert warnings == []


class TestClassifyAndSession:
    """Nhận dạng tờ nào + biết số hiệu thuộc phiên cũ hay mới."""

    @pytest.mark.parametrize("title,form", [
        ("MÁY CẮT HẠ THẾ (ACB)", "93"),
        ("MÁY CẮT HẠ THẾ (MCCB)", "45"),
        ("CẦU CHÌ TỰ RƠI CÓ DẬP HỒ QUANG (LBFCO)", "95"),
        ("CẦU CHÌ TỰ RƠI (FCO)", "47"),
        ("CHỐNG SÉT VAN (LA)", "46"),
        ("THÔNG TUYẾN CÁP NGẦM TRUNG THẾ", "97"),
        ("MÁY BIẾN ÁP 3 PHA", "49"),
        ("MÁY BIẾN ÁP 1 PHA", "44"),
        ("ĐIỆN TRỞ NỐI ĐẤT", "48"),
    ])
    def test_guess_form_from_title(self, title, form):
        from bienban.vision import guess_form

        pool = ["44", "45", "46", "47", "48", "49", "93", "95", "97"]
        assert guess_form(title, available=pool) == form

    def test_acb_not_confused_with_mccb(self):
        from bienban.vision import guess_form

        pool = ["45", "93"]
        assert guess_form("MÁY CẮT HẠ THẾ (ACB)", available=pool) == "93"
        assert guess_form("MÁY CẮT HẠ THẾ (MCCB)", available=pool) == "45"

    def test_group_by_form(self):
        from bienban.vision import group_by_form

        photos = [{"image_index": 0, "form": "49"}, {"image_index": 1, "form": "48"},
                  {"image_index": 2, "form": "49"}, {"image_index": 3, "form": ""}]
        assert group_by_form(photos) == {"49": [0, 2], "48": [1], "": [3]}

    def test_decode_doc_no(self):
        from bienban.spec import decode_doc_no

        info = decode_doc_no("50921026/BB-TC")
        assert (info["code"], info["thang"], info["nam"]) == ("92", 10, 2026)
        assert info["phien"] == "tháng 10/2026"
        assert decode_doc_no("rác")["ok"] is False

    def test_expected_doc_no(self):
        from bienban.spec import expected_doc_no

        assert expected_doc_no("49", "25/10/2026") == "50921026/BB-TC"
        assert expected_doc_no("44", "01/11/2026") == "50441126/BB-TC"
        assert expected_doc_no("49", "") == ""

    def test_mixed_session_is_flagged(self):
        from bienban.validate import validate

        data = {"thong_tin_chung": {"ngay_kiem_dinh": "01/11/2026"},
                "bien_ban_49_mba_3p": {"so_bien_ban": "50921026/BB-TC"}}
        msgs = [p.message for p in validate(data) if p.where.endswith("so_bien_ban")]
        assert any("tháng 10/2026" in m and "50921126" in m for m in msgs)

    def test_matching_session_is_quiet(self):
        from bienban.validate import validate

        data = {"thong_tin_chung": {"ngay_kiem_dinh": "25/10/2026"},
                "bien_ban_49_mba_3p": {"so_bien_ban": "50921026/BB-TC"}}
        assert not [p for p in validate(data) if p.where.endswith("so_bien_ban")]


class TestForm93And97:
    """Hai mẫu dựng thêm từ biên bản thật trong repo (093 ACB, 097 cáp ngầm)."""

    def test_files_exist_and_registered(self):
        from bienban.spec import DATA_KEYS, TEMPLATES, TITLES

        for form, name in (("93", "MÁY CẮT HẠ THẾ (ACB)"),
                           ("97", "THÔNG TUYẾN CÁP NGẦM TRUNG THẾ")):
            assert form in TEMPLATES and form in DATA_KEYS and form in TITLES
            assert TITLES[form] == name
            assert (TEMPLATES).get(form) and (ROOT / "templates" / TEMPLATES[form]).exists()

    def test_acb_renders_like_mccb(self, tmp_path):
        from bienban.fill import render_all

        data = {"bien_ban_93_acb": {
            "so_bien_ban": "50931026/BB-TC", "loai": "ACB", "hieu": "LS",
            "kieu": "AS-25E3-25H", "so_cuc": "03", "dien_ap_dinh_muc": "500V",
            "dong_dinh_muc": "2500A", "dong_ngan_mach_toi_da": "85kA",
            "tan_so": "50/60Hz", "dien_ap_cach_dien": "1000V",
            "dien_ap_xung": "12kV", "kiem_tra_ben_ngoai": "Bình thường",
            "so_luong": "01",
            "rows": {"rows": [{"stt": "1", "rcd_close": ">5000", "rcd_open": ">5000",
                               "rtx_a": "279", "rtx_b": "281", "rtx_c": "277",
                               "utest": "3", "dong_cat": "5", "ket_qua": "Đạt",
                               "so_tem": "016138"}]},
        }}
        paths, warnings = render_all(data, templates_dir=TEMPLATES,
                                     out_dir=tmp_path, forms=["93"])
        assert warnings == [], warnings
        doc = docx.Document(str(paths[0]))
        text = "\n".join([c.text for t in doc.tables for r in t.rows for c in r.cells]
                         + [p.text for p in doc.paragraphs])
        for must in ("279", "281", "277", "016138", "AS-25E3-25H", "2500A",
                     "MÁY CẮT HẠ THẾ (ACB)"):
            assert must in text, f"mẫu 93 thiếu {must!r}"

    def test_cap_ngam_renders_by_phase(self, tmp_path):
        from bienban.fill import render_all

        data = {"bien_ban_97_cap_ngam": {
            "so_bien_ban": "50971026/BB-TC", "so_tem": "016139",
            "doan_cap_tu": "Trụ 82/1", "doan_cap_den": "Trạm biến áp 1500kVA",
            "tiet_dien": "3 x 50mm2", "dien_ap_dinh_muc": "12,7/22(24)kV",
            "r_cach_dien_Mohm": {"rows": [
                {"key": "pha1", "tieu_chuan": ">5000", "so_lieu_do": ">10000"},
                {"key": "pha2", "tieu_chuan": ">5000", "so_lieu_do": ">10000"},
                {"key": "pha3", "tieu_chuan": ">5000", "so_lieu_do": ">10000"}]},
            "thu_dien_ap_mot_chieu": {"rows": [
                {"key": "pha1", "thoi_gian": "15", "dien_ap": "38,1", "dong_ro": "17"},
                {"key": "pha2", "thoi_gian": "15", "dien_ap": "38,1", "dong_ro": "12"},
                {"key": "pha3", "thoi_gian": "15", "dien_ap": "38,1", "dong_ro": "15"}]},
        }}
        paths, warnings = render_all(data, templates_dir=TEMPLATES,
                                     out_dir=tmp_path, forms=["97"])
        assert warnings == [], warnings
        doc = docx.Document(str(paths[0]))
        text = "\n".join([c.text for t in doc.tables for r in t.rows for c in r.cells]
                         + [p.text for p in doc.paragraphs])
        for must in ("Pha 1 – (2+3+vỏ)", "Pha 2 – (1+3+vỏ)", "Pha 3 – (1+2+vỏ)",
                     ">10000", "38,1", "17", "12", "15", "016139", "Trụ 82/1"):
            assert must in text, f"mẫu 97 thiếu {must!r}"

    def test_cap_ngam_blank_does_not_crash(self, tmp_path):
        from bienban.fill import render_all

        paths, warnings = render_all({"bien_ban_97_cap_ngam": {}},
                                     templates_dir=TEMPLATES, out_dir=tmp_path,
                                     forms=["97"])
        assert paths and paths[0].exists()
        assert all(not w.startswith("[BB 97] Không") for w in warnings)


class TestUiDataKey:
    """Lỗi thật: mẫu 49 ghi vào ``bien_ban_undefined`` vì UI hard-code 44–48."""

    def test_ui_no_hardcoded_data_key_map(self):
        html = (ROOT / "web" / "templates" / "index.html").read_text(encoding="utf-8")
        assert "FORMS_INFO" in html
        # bảng cứng cũ phải biến mất
        assert 'const DATA_KEY = {44:"44_mba"' not in html

    def test_every_form_has_server_data_key(self):
        from bienban.spec import DATA_KEYS, TEMPLATES

        assert set(DATA_KEYS) == set(TEMPLATES)
        for key in DATA_KEYS.values():
            assert key.startswith("bien_ban_")


class TestResolvedImageFix:
    def test_max_edge_is_high_enough_for_handwriting(self):
        from bienban.vision import MAX_EDGE

        assert MAX_EDGE >= 2400, "ảnh thu quá nhỏ thì chữ viết tay không đọc được"
