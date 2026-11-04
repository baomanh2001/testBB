# Biên bản kiểm định điện lực — tool tự động điền mẫu 44–48

Bộ công cụ nhận **JSON** (kết quả trích xuất từ ảnh hiện trường) rồi sinh ra
5 biên bản Word chuẩn form của Công ty CP Thí nghiệm Điện Toàn Cầu:

| Mã | Biên bản | Mẫu Word |
|----|----------|----------|
| 44 | Máy biến áp 1 pha | `templates/44 BB MBA 1P.docx` |
| 45 | Máy cắt hạ thế (MCCB) | `templates/45 MCCB 250A.docx` |
| 46 | Chống sét van (LA) | `templates/46 BB LA.docx` |
| 47 | Cầu chì tự rơi (FCO) | `templates/47 BB FCO.docx` |
| 48 | Điện trở nối đất | `templates/48 BB điện trở nối đất.docx` |

Điểm quan trọng: tool **không dựng lại tài liệu**, chỉ thay phần chữ. Logo,
header/footer, khổ A4, đánh số La Mã (I, II, III…), kẻ bảng, watermark và chữ
ký số của mẫu gốc được giữ nguyên 100% — nên mở bằng Word vẫn đúng form.

---

## 1. Cài đặt

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Chỉ cần `python-docx` (và `Flask` nếu dùng web UI). Không cần LibreOffice,
không cần Microsoft Word, không cần Node.

## 2. Chạy nhanh

```bash
# sinh 5 biên bản từ dữ liệu mẫu E-GREEN 01/11/2026
./.venv/bin/python -m bienban fill samples/e-green-01112026.json -o output

# kiểm tra JSON trước khi điền (bắt lỗi ngày sai, thiếu số máy, dấu . thay vì ,)
./.venv/bin/python -m bienban check data.json

# in khung JSON rỗng để điền tay
./.venv/bin/python -m bienban template -o data.json

# chỉ sinh một vài biên bản
./.venv/bin/python -m bienban fill data.json --forms 44,48 -o output

# in đậm + in hoa phần giá trị của Tên công trình / Địa chỉ / Kết luận
./.venv/bin/python -m bienban fill data.json --company-accent -o output

# đọc JSON từ stdin
cat data.json | ./.venv/bin/python -m bienban fill - -o output
```

Kết quả trong `output/`:

```
44_50441126BBTC.docx
45_50451126BBTC.docx
46_50461126BBTC.docx
47_50471126BBTC.docx
48_50481126BBTC.docx
```

## 3. Web UI (dán JSON → **xem trước** → tải file)

```bash
./.venv/bin/python web/app.py          # http://127.0.0.1:8000
PORT=8080 ./.venv/bin/python web/app.py
```

Bấm **“Xem trước & sinh biên bản”** là thấy ngay **bản in** của từng biên bản
đúng như file Word sẽ xuất ra (logo, bảng tiêu đề SỐ/NGÀY, đánh số I/II/III,
bảng kẻ gộp ô, số liệu, chữ ký, footer) — soát xong mới tải file:

* tab **44 … 48** để chuyển nhanh giữa 5 biên bản
* nút **⬇ Tải** trên từng file, **⬇ Tải tất cả (.zip)**
* **Tab riêng** mở bản xem trước toàn trang (in ra PDF được nếu cần)

> Vì sao tải bằng link `/download/<token>/<file>` chứ không phải blob: trong
> iframe preview (Arena, Zalo, Facebook…) nhiều trình duyệt chặn tải file sinh
> ra bằng `URL.createObjectURL`. Link GET thật thì luôn tải được. File được
> lưu tạm 6 giờ rồi tự dọn.

Xem trước dùng được cả từ Python:

```python
from bienban.preview import docx_to_html
html = docx_to_html("output/45_50451126BBTC.docx")   # khối HTML + logo base64
```

## 4. JSON đầu vào

Xem `samples/e-green-01112026.json` (dữ liệu thật từ 7 ảnh biên bản viết tay +
1 ảnh công tơ) và `prompts/extract.md` (prompt để LLM đọc ảnh xuất ra đúng
cấu trúc này).

```jsonc
{
  "thong_tin_chung": {
    "ten_cong_trinh": "...", "dia_chi": "...", "don_vi_yeu_cau": "...",
    "ly_do_kiem_dinh": "Sau sự cố", "noi_kiem_dinh": "Tại hiện trường",
    "ngay_kiem_dinh": "01/11/2026", "ngay_lap_bien_ban": "04/11/2026",
    "can_bo_ky_ten": {"nguoi_thu": "...", "nguoi_kiem_tra": "...", "p_giam_doc": "..."}
  },
  "cong_to_dien": { ... },                    // lưu kèm, hiện chưa in ra biên bản
  "bien_ban_44_mba": { ... },
  "bien_ban_45_mccb": { ... },
  "bien_ban_46_la": { ... },
  "bien_ban_47_fco": { ... },
  "bien_ban_48_tiep_dat": { ... }
}
```

Biên bản nào **không có khoá** thì tool bỏ qua, không sinh file rỗng.

### Quy tắc dữ liệu được áp tự động

| Đầu vào | Ghi ra Word | Ghi chú |
|---|---|---|
| `"1/11/2026"` | `01/11/2026` | mọi ngày về `dd/mm/yyyy` |
| `"3.52"` / `3.52` | `3,52` | số đo luôn dùng dấu phẩy thập phân VN |
| `">5000"`, `"10 kA"` | giữ nguyên | không đổi đơn vị / dấu so sánh |
| `"O17l246"` (OCR) | `017246` | số máy / số tem chỉ giữ chữ số |
| `"01"` | `Một (01)` | số lượng trong câu kết luận |
| thiếu `ket_luan` | tự sinh câu chuẩn | `Một (01) <thiết bị> trên đạt yêu cầu đóng điện vận hành` |
| thiếu trường phụ | `-` | giữ đúng quy ước của mẫu |

## 5. Cấu hình (tuỳ chọn)

```bash
./.venv/bin/python -m bienban fill data.json -c config.json
```

Sao chép `config.example.json` → `config.json` rồi sửa. Các nhóm chính:

* `style.header_values`: `"template"` (mặc định — giữ đúng định dạng mẫu,
  đúng biên bản công ty đang dùng) hoặc `"bold_upper"` (in đậm + in hoa phần
  giá trị Tên công trình / Địa chỉ / Kết luận, nhãn giữ nguyên).
* `defaults`: tần số, số pha, loại thiết bị, thiết bị đo, thời gian thử…
* `conclusions.default_template`: mẫu câu kết luận.
* `forms`: giới hạn các biên bản được phép sinh.

> Vì sao mặc định là `template`: cả 5 file mẫu hiện hành đều in giá trị ở dạng
> chữ thường (đúng biên bản đã phát hành). Cần “Bold + IN HOA” thì bật
> `--company-accent` hoặc đặt `style.header_values = "bold_upper"`.

## 6. Cách hoạt động

```
ảnh hiện trường
      │  (LLM / người đọc — xem prompts/extract.md)
      ▼
JSON chuẩn ──► validate ──► điền Word ──► 5 file .docx
                              │
                              ├─ lớp 1: khung (SỐ, NGÀY, tiêu đề thiết bị)
                              ├─ lớp 2: các ô "Nhãn: giá trị" (kể cả 2–3 ô/dòng)
                              └─ lớp 3: bảng số liệu (cách điện, R một chiều,
                                        tỉ số biến áp, MCCB, LA, FCO, nối đất)
```

Ba điểm kỹ thuật đáng chú ý:

1. **Không ghi đè chéo ô.** Mẫu dàn 2 ô trên một dòng bằng `TAB + "-"`. Bộ
   điền cắt dòng theo `\t-` nên mỗi giá trị chỉ thay đúng phần của mình:
   `Hiệu: MITSUBISHI` và `Số cực: 03` độc lập.
2. **Nhãn khớp chính xác.** So khớp bỏ dấu, không phân biệt hoa/thường, nhưng
   bắt buộc **đứng đầu từ + có dấu `:`** → `IN` không khớp nhầm vào `NGHIỆM`,
   `Hiệu` không khớp vào `Hiệu máy`.
3. **Bảng nhận theo “neo”.** Mỗi bảng có bộ khoá riêng + số cột tối thiểu, nên
   bảng *tỉ số biến áp* không bị nhận nhầm thành bảng *R một chiều*.

## 7. Mẫu 44 (.doc cũ)

`44 BB MBA 1P 50KVA.doc` là Word 97. Để điền form đồng nhất, mẫu 44 đã được
dựng lại thành `templates/44 BB MBA 1P.docx` bằng `tools/build_template_44.py`:
nhân bản khung (style, 3 header logo, footer, khổ giấy, lề) của `45 MCCB 250A.docx`
rồi chép nguyên nội dung bản .doc (đúng thứ tự mục I → V, đúng nhãn, đúng đơn vị).

```bash
./.venv/bin/python tools/build_template_44.py
```

Bản .doc gốc được giữ tại `legacy/44 BB MBA 1P 50KVA.doc` để đối chiếu.

## 8. Kiểm thử

```bash
./.venv/bin/python -m pytest -q      # 47 test
```

Bao gồm: chuẩn hoá ngày/số, nhận dạng nhãn, nội dung từng biên bản 44–48,
giữ header/footer + ảnh logo, chế độ in đậm/in hoa, validate dữ liệu, dựng bản
xem trước HTML (logo, gộp ô, số liệu) và API web (render / download / preview).

## 9. Cấu trúc thư mục

```
bienban/            # thư viện chính
  normalize.py      #   chuẩn hoá ngày, số, đọc số thành chữ
  spec.py           #   "hợp đồng dữ liệu": nhãn ↔ đường dẫn JSON cho từng mẫu
  labels.py         #   điền ô "Nhãn: giá trị"
  ooxml.py          #   thao tác XML Word (giữ định dạng gốc)
  fill.py           #   điều phối + điền bảng + chữ ký + kết luận
  validate.py       #   kiểm tra JSON trước khi điền
  preview.py        #   dựng bản xem trước HTML từ file .docx
  __main__.py       #   CLI (fill / check / template / forms)
templates/          # 5 mẫu Word đang dùng
legacy/             # bản .doc gốc của mẫu 44
samples/            # JSON mẫu (dữ liệu thật E-GREEN 01/11/2026)
prompts/extract.md  # prompt trích xuất ảnh → JSON
tools/              # script dựng lại mẫu 44
web/                # Flask UI
tests/              # pytest
output/             # file .docx sinh ra (đã .gitignore)
```

## 10. Mở rộng

* **Thêm mẫu mới**: thêm file vào `templates/`, khai báo `TEMPLATES`, `TITLES`,
  `DATA_KEYS`, `LABELS` trong `bienban/spec.py` (và `TABLE_PROBES` nếu có bảng).
* **Đổi nhãn trong mẫu Word**: sửa `LABELS` — không cần chạm vào code điền.
* **Đổi định dạng in**: sửa `config.json` mục `style`.
