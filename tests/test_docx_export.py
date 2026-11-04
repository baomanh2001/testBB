import base64
import io
import zipfile
import docx
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_and_static_index():
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert len(data["supported_templates"]) == 10

    idx = client.get("/")
    assert idx.status_code == 200
    assert "CÔNG TY CP THÍ NGHIỆM ĐIỆN TOÀN CẦU" in idx.text


@pytest.mark.parametrize("station,count", [("dream_mekong", 7), ("egreen", 5)])
def test_samples_and_docx_exports(station, count):
    resp = client.get("/api/samples", params={"station": station})
    assert resp.status_code == 200
    batch = resp.json()
    reports = batch["reports"]
    assert len(reports) == count

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
        assert rep["common"]["ten_cong_trinh"] in combined
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


@pytest.mark.parametrize("report_type", ["mba_1p", "mba_3p", "mccb", "acb", "la", "fco", "lbfco", "dtnd", "cap_ngam", "tu_bu"])
def test_empty_data_does_not_import_example_measurements(report_type):
    response = client.post("/api/export/docx", json={
        "report_type": report_type,
        "common": {"ten_cong_trinh": "Công trình thử nghiệm riêng", "dia_chi": "", "don_vi_yeu_cau": ""},
        "data": {},
    })
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        xml = z.read("word/document.xml").decode()
        assert "Công trình thử nghiệm riêng" in xml
        # These values are from the examples, not from the request.
        for value in ("103150017", "3,413", "017246", "MITSUBISHI", "164,3", "Trụ 82/1"):
            assert value not in xml


def test_partial_measurement_row_is_not_completed_from_examples():
    response = client.post("/api/export/docx", json={
        "report_type": "acb", "data": {"rows": [{"rtx_a": "123,45"}]}
    })
    assert response.status_code == 200
    doc = docx.Document(io.BytesIO(response.content))
    cells = [cell.text for cell in doc.tables[1].rows[2].cells]
    assert cells[3] == "123,45"
    assert cells[1] == cells[2] == cells[4] == cells[8] == ""


def test_mccb_retains_original_standard_section_layout():
    sample = next(r for r in client.get('/api/samples?station=egreen').json()['reports'] if r['report_type'] == 'mccb')
    response = client.post('/api/export/docx', json=sample)
    doc = docx.Document(io.BytesIO(response.content))
    paragraphs = [p.text for p in doc.paragraphs]
    assert 'V.\tTIÊU CHUẨN KIỂM ĐỊNH:' in paragraphs
    idx = paragraphs.index('V.\tTIÊU CHUẨN KIỂM ĐỊNH:')
    assert sample['data']['tieu_chuan_kiem_dinh'] in paragraphs[idx + 1]
    assert paragraphs[idx + 2].startswith('VI.\tKẾT LUẬN:')


def test_tu_bu_preserves_row_values_and_order():
    sample = next(r for r in client.get('/api/samples').json()['reports'] if r['report_type'] == 'tu_bu')
    sample['data']['tu_bu_rows'] = [
        {'stt': '1', 'dung_luong': '10', 'r_cach_dien': '>2000', 'dien_dung': '164,3', 'ket_qua': 'Đạt'},
        {'stt': '2', 'dung_luong': '20', 'r_cach_dien': '>3000', 'dien_dung': '312,9', 'ket_qua': 'Đạt'},
    ]
    response = client.post('/api/export/docx', json=sample)
    doc = docx.Document(io.BytesIO(response.content))
    rows = doc.tables[4].rows
    assert [c.text for c in rows[1].cells] == ['1', '10', '>2000', '164,3', 'Đạt']
    assert [c.text for c in rows[2].cells] == ['2', '20', '>3000', '312,9', 'Đạt']


def test_vietnamese_text_and_case_are_preserved():
    sample = next(r for r in client.get('/api/samples?station=egreen').json()['reports'] if r['report_type'] == 'la')
    sample['common']['ten_cong_trinh'] = 'Trạm biến áp An Hội – CÔNG TY TNHH Điện Ánh Dương'
    sample['data']['ket_luan'] = 'Đã kiểm tra; cần đối chiếu trước khi đóng điện.'
    sample['data']['rows'][0]['doi_tuong_do'] = 'Pha C – Đầu trên'
    response = client.post('/api/export/docx', json=sample)
    assert response.status_code == 200
    doc = docx.Document(io.BytesIO(response.content))
    paragraphs = '\n'.join(p.text for p in doc.paragraphs)
    assert sample['common']['ten_cong_trinh'] in paragraphs
    assert sample['data']['ket_luan'] in paragraphs
    assert doc.tables[1].rows[1].cells[0].text == 'Pha C – Đầu trên'
    assert 'CHỐNG SÉT VAN (LA)' in paragraphs


def test_sample_mba_discrepancy_is_disclosed():
    sample = client.get('/api/samples?station=dream_mekong').json()['reports'][0]
    assert any('khác' in note and 'nhiệt độ' in note for note in sample['ai_notes'])


@pytest.mark.parametrize("station,report_type,headings", [
    ("egreen", "mba_1p", ["LÝ LỊCH THIẾT BỊ", "QUY CÁCH KỸ THUẬT", "KẾT QUẢ KIỂM ĐỊNH", "THIẾT BỊ KIỂM ĐỊNH", "KẾT LUẬN"]),
    ("dream_mekong", "mba_3p", ["LÝ LỊCH THIẾT BỊ", "QUY CÁCH KỸ THUẬT", "KẾT QUẢ KIỂM ĐỊNH", "THIẾT BỊ KIỂM ĐỊNH", "KẾT LUẬN"]),
    ("egreen", "mccb", ["THÔNG TIN CÔNG TRÌNH", "THÔNG SỐ THIẾT BỊ", "KẾT QUẢ KIỂM ĐỊNH", "THIẾT BỊ KIỂM ĐỊNH", "TIÊU CHUẨN KIỂM ĐỊNH", "KẾT LUẬN"]),
    ("dream_mekong", "acb", ["THÔNG TIN CÔNG TRÌNH", "THÔNG SỐ THIẾT BỊ", "KẾT QUẢ THỬ NGHIỆM", "THIẾT BỊ THỬ NGHIỆM", "TIÊU CHUẨN THỬ NGHIỆM", "KẾT LUẬN"]),
    ("egreen", "la", ["THÔNG TIN CÔNG TRÌNH", "THÔNG SỐ THIẾT BỊ", "KẾT QUẢ KIỂM ĐỊNH", "TIÊU CHUẨN KIỂM ĐỊNH", "THIẾT BỊ KIỂM ĐỊNH", "KẾT LUẬN"]),
    ("egreen", "fco", ["THÔNG TIN CÔNG TRÌNH", "THÔNG SỐ THIẾT BỊ", "KẾT QUẢ KIỂM ĐỊNH", "TIÊU CHUẨN KIỂM ĐỊNH", "THIẾT BỊ KIỂM ĐỊNH", "KẾT LUẬN"]),
    ("dream_mekong", "lbfco", ["THÔNG TIN CÔNG TRÌNH", "THÔNG SỐ THIẾT BỊ", "KẾT QUẢ KIỂM ĐỊNH", "TIÊU CHUẨN KIỂM ĐỊNH", "THIẾT BỊ KIỂM ĐỊNH", "KẾT LUẬN"]),
    ("egreen", "dtnd", ["THÔNG TIN CÔNG TRÌNH", "KẾT QUẢ THỬ NGHIỆM", "THIẾT BỊ THỬ NGHIỆM", "GHI CHÚ"]),
    ("dream_mekong", "cap_ngam", ["THÔNG TIN CÔNG TRÌNH", "THÔNG SỐ THIẾT BỊ", "KẾT QUẢ KIỂM ĐỊNH", "THIẾT BỊ KIỂM ĐỊNH", "KẾT LUẬN"]),
    ("dream_mekong", "tu_bu", ["THÔNG TIN CÔNG TRÌNH", "KẾT QUẢ KIỂM ĐỊNH", "THIẾT BỊ KIỂM ĐỊNH", "TIÊU CHUẨN KIỂM ĐỊNH", "KẾT LUẬN"]),
])
def test_visible_roman_headings_and_accents(station, report_type, headings):
    sample = next(r for r in client.get('/api/samples', params={'station': station}).json()['reports'] if r['report_type'] == report_type)
    result = client.post('/api/export/docx', json=sample)
    assert result.status_code == 200
    document = docx.Document(io.BytesIO(result.content))
    roman = ['I.', 'II.', 'III.', 'IV.', 'V.', 'VI.']
    for number, heading in zip(roman, headings):
        expected = f'{number}\t{heading}'
        paragraph = next(p for p in document.paragraphs if p.text.startswith(expected))
        assert paragraph.runs[0].bold  # Visible section number is bold too.
        assert paragraph.runs[1].bold  # Vietnamese heading is explicitly bold.
        assert not paragraph._p.xpath('./w:pPr/w:numPr')  # No duplicate auto number.
    assert any(p.text.startswith('-\tTên công trình: ') for p in document.paragraphs)


def test_lbfco_numbered_subsections_and_table_match_reference():
    sample = next(r for r in client.get('/api/samples').json()['reports'] if r['report_type'] == 'lbfco')
    result = client.post('/api/export/docx', json=sample)
    document = docx.Document(io.BytesIO(result.content))
    paragraphs = [p.text for p in document.paragraphs]
    assert '1.\tKiểm tra bên ngoài: Bình thường\t- Số lượng: 03 Bộ' in paragraphs
    assert '2.\tKết quả kiểm định:' in paragraphs
    table = document.tables[1]
    assert len(table.rows) == 5
    assert [table.cell(i, 0).text for i in (2, 3, 4)] == ['LBFCO 01', 'LBFCO 02', 'LBFCO 03']
    assert [c.text for c in table.rows[2].cells] == ['LBFCO 01', '>10000', '>10000', '60', '50', '5', 'Đạt']
    assert any(p.startswith('IV.\tTIÊU CHUẨN KIỂM ĐỊNH:') for p in paragraphs)
    assert any(p.startswith('V.\tTHIẾT BỊ KIỂM ĐỊNH:') for p in paragraphs)
    assert any(p.startswith('VI.\tKẾT LUẬN:') for p in paragraphs)
