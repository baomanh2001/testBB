import base64
import io
import zipfile
import docx
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_and_static_index():
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert len(data["supported_templates"]) == 5

    idx = client.get("/")
    assert idx.status_code == 200
    assert "CÔNG TY CP THÍ NGHIỆM ĐIỆN TOÀN CẦU" in idx.text


def test_samples_and_all_5_docx_exports():
    resp = client.get("/api/samples")
    assert resp.status_code == 200
    batch = resp.json()
    reports = batch["reports"]
    assert len(reports) == 5

    # Verify sample image serving works
    first_img_url = reports[0]["images"][0]["url"]
    img_resp = client.get(first_img_url)
    assert img_resp.status_code == 200
    assert img_resp.headers["content-type"] == "image/jpeg"

    # Export each of the 5 reports individually and verify .docx contents
    for rep in reports:
        payload = {
            "report_type": rep["report_type"],
            "filename": rep["filename"],
            "common": rep["common"],
            "signatory": rep["signatory"],
            "data": rep["data"],
        }
        exp = client.post("/api/export/docx", json=payload)
        assert exp.status_code == 200
        assert "officedocument.wordprocessingml.document" in exp.headers["content-type"]

        # Verify valid ZIP & Word media (logo + signature + watermark)
        with zipfile.ZipFile(io.BytesIO(exp.content)) as zf:
            names = set(zf.namelist())
            assert "word/document.xml" in names
            assert "word/media/image1.jpeg" in names  # Company logo
            assert "word/media/image2.png" in names   # Tester signature
            assert "word/media/image3.jpeg" in names  # Watermark

        d = docx.Document(io.BytesIO(exp.content))
        full_text = "\n".join(p.text for p in d.paragraphs)
        tbl_text = "\n".join(
            cell.text for tbl in d.tables for row in tbl.rows for cell in row.cells
        )
        combined = full_text + "\n" + tbl_text
        assert rep["common"]["so_bien_ban"] in combined
        assert "DOANH NGHIỆP TƯ NHÂN E-GREEN" in combined
        assert "Nguyễn Trung Nghĩa" in combined
        assert "Nguyễn Minh Quân" in combined
        assert "Nguyễn Nhật Tân" in combined


def test_dynamic_multi_row_and_signature_toggle_and_zip():
    # Test 3-phase FCO (3 rows) + signature disabled
    payload_fco_3 = {
        "report_type": "fco",
        "filename": "47 BB FCO 3 pha.docx",
        "common": {
            "so_bien_ban": "50991126/BB-TC",
            "ngay_phat_hanh": "04/11/2026",
            "loai_tieu_de": "BIÊN BẢN KIỂM ĐỊNH",
            "ten_cong_trinh": "Trạm biến áp 250kVA – CÔNG TY TNHH ABC",
            "dia_chi": "TP.HCM",
            "chi_danh": "FCO – 100A",
            "don_vi_yeu_cau": "CÔNG TY TNHH ABC",
            "ly_do": "Định kỳ",
            "noi_kiem_dinh": "Tại hiện trường",
            "ngay_kiem_dinh": "04/11/2026",
        },
        "signatory": {
            "nguoi_thu": "Kỹ sư A",
            "kiem_tra": "Kỹ sư B",
            "pho_giam_doc": "Nguyễn Nhật Tân",
            "include_signature": False,
        },
        "data": {
            "vat_lieu_cach_dien": "Polymer",
            "dong_dien_dinh_muc": "100A",
            "dien_ap_dinh_muc": "24kV",
            "kha_nang_cat_ngan_mach": "12kA",
            "kiem_tra_ben_ngoai": "Bình thường",
            "so_luong": "03",
            "rows": [
                {"thiet_bi": "FCO 01", "rcd_truoc": ">10000", "rcd_sau": ">10000", "ac_kho": "60", "ac_uot": "50", "dong_cat": "5", "ket_qua": "Đạt"},
                {"thiet_bi": "FCO 02", "rcd_truoc": ">10000", "rcd_sau": ">10000", "ac_kho": "60", "ac_uot": "50", "dong_cat": "5", "ket_qua": "Đạt"},
                {"thiet_bi": "FCO 03", "rcd_truoc": ">10000", "rcd_sau": ">10000", "ac_kho": "60", "ac_uot": "50", "dong_cat": "5", "ket_qua": "Đạt"},
            ],
        },
    }
    r = client.post("/api/export/docx", json=payload_fco_3)
    assert r.status_code == 200
    d = docx.Document(io.BytesIO(r.content))
    # Table[1] has 2 header rows + 3 data rows = 5 rows
    assert len(d.tables[1].rows) == 5

    # Test custom signature PNG swap + batch .zip export
    fake_png = base64.b64encode(b"\x89PNG\r\n\x1a\nFAKE_CUSTOM_SIG").decode("ascii")
    payload_fco_3["signatory"]["include_signature"] = True
    payload_fco_3["signatory"]["custom_signature_data_url"] = f"data:image/png;base64,{fake_png}"

    zip_resp = client.post(
        "/api/export/zip",
        json={"zip_filename": "Ho_so_test.zip", "reports": [payload_fco_3]},
    )
    assert zip_resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zbatch:
        assert "47 BB FCO 3 pha.docx" in zbatch.namelist()
        inner_docx = zbatch.read("47 BB FCO 3 pha.docx")
        with zipfile.ZipFile(io.BytesIO(inner_docx)) as zdoc:
            assert zdoc.read("word/media/image2.png") == b"\x89PNG\r\n\x1a\nFAKE_CUSTOM_SIG"
