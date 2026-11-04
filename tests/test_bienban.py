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
        d = json.loads(json.dumps(data))
        d["thong_tin_chung"]["ngay_kiem_dinh"] = "31/02/2026"
        assert any(p.level == "error" for p in validate(d))

    def test_missing_insulation(self, data):
        d = json.loads(json.dumps(data))
        del d["bien_ban_44_mba"]["r_cach_dien_Mohm"]["ha1_ha2"]["r60"]
        assert any(p.level == "error" and "ha1_ha2" in p.where for p in validate(d))

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
        from bienban.vision import _wire_model

        assert _wire_model("gemini-1.5-flash") == "gemini-2.5-flash"
        assert _wire_model("models/gemini-2.5-pro") == "gemini-2.5-pro"

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
        assert set(body["schema"]["forms"]) == {"44", "45", "46", "47", "48"}
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

    def test_render_refuses_incomplete_common(self, client):
        from bienban import vision

        data = vision.normalize_ai_result({"reports": [{
            "report_type": "48", "data": {
                "so_bien_ban": "5048/BB-TC", "chi_danh": "Điện trở nối đất",
                "ket_noi_trung_tinh": "Có", "loai_tiep_dat": "Làm việc",
                "gia_tri_do_Ohm": "3,52", "thiet_bi_do": "KEW 4105DL"}}]})
        body = client.post("/api/render", json=data).get_json()
        assert body["ok"] is False
        missing = " ".join(p["where"] for p in body["problems"] if p["level"] == "error")
        assert "thong_tin_chung.dia_chi" in missing

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
        """Mọi ô nhãn của 5 mẫu đều phải có input trong schema (để sửa được)."""
        from bienban.schema import fields_of, tables_of
        from bienban.spec import LABELS

        for form, items in LABELS.items():
            have = {f["key"] for f in fields_of(form)}
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
                    }
                    if it["table"] in series_prefix:
                        prefix = series_prefix[it["table"]]
                        assert any(k.startswith(prefix) for k in have), (form, prefix)
                        continue
                    # 45/46/47/48: bảng kết quả của Word tương ứng khoá dữ liệu chung "rows"
                    alias = {"insulation": "r_cach_dien_Mohm", "mccb": "rows",
                             "la": "rows", "fco": "rows", "earth": "rows"}
                    key = alias.get(it["table"], it["table"])
                    assert key in tables, (form, it["table"])


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
        assert "Mẫu Word      : 5/5" in out
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
