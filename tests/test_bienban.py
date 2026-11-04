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
        assert "Điền biên bản" in r.get_data(as_text=True)

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
