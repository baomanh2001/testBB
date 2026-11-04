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

## 1. Chạy nhanh nhất — bấm đúp, không gõ lệnh

### Windows

Bấm đúp **`Chay-Web.bat`**. Lần đầu nó tự làm hết:

1. tìm Python (nếu chưa có thì mở trang tải),
2. tạo môi trường `.venv` và cài thư viện,
3. hỏi **API key Gemini một lần** rồi lưu vào `.env` (lần sau khỏi nhập),
4. bật server và **tự mở trình duyệt**.

Có trục trặc thì bấm đúp **`Chay-Nhanh.bat`** — nó chỉ kiểm tra môi trường rồi
in ra đang thiếu gì, không mở server.

> Nếu Windows hiện cảnh báo "Windows protected your PC": bấm **More info** →
> **Run anyway** (file .bat chỉ là script đọc được bằng Notepad, không phải
> file cài đặt).

### macOS

Bấm đúp **`Chay-Web.command`** (macOS chỉ cho bấm đúp file đuôi `.command`).
Nếu macOS chặn: chuột phải → **Open** → **Open** một lần là xong.

### Linux

```bash
./chay-web.sh
```

Ba file trên làm y hệt nhau: tự cài môi trường, hỏi key 1 lần, mở trình duyệt.
Dùng chung một lõi là `launcher.py`:

```bash
python launcher.py                # chạy bình thường
python launcher.py --port 8090    # đổi cổng (8000 bận thì tự nhảy cổng khác)
python launcher.py --no-browser   # không tự mở trình duyệt
python launcher.py --check        # chỉ kiểm tra môi trường rồi thoát
```

Khi server chạy, muốn dùng trên **điện thoại cùng wifi** thì mở
`http://<IP-máy-tính>:8000` (server nghe trên `0.0.0.0`). Dừng bằng `Ctrl + C`.

### API key Gemini — 3 cách, chọn 1

| Cách | Làm gì |
|---|---|
| **Tự động (khuyến nghị)** | Cứ bấm `Chay-Web.bat` / `Chay-Web.command`, nó hỏi key 1 lần rồi lưu vào `.env` (quyền `600`, đã gitignore) |
| **Biến môi trường** | `export GEMINI_API_KEY=AIza...` (Linux/macOS) hoặc `set GEMINI_API_KEY=AIza...` (Windows) |
| **Trên giao diện** | Dán vào ô “API key Gemini” — chỉ đi theo header của request, không lưu ổ đĩa server |

Lấy key miễn phí: <https://aistudio.google.com/apikey>. Không có key vẫn dùng
được toàn bộ phần còn lại (dán JSON, sửa form, xem trước, tải Word) — chỉ là
không nhận dạng ảnh được.

Sao lưu cấu hình: copy `.env.example` thành `.env` rồi điền tay.

## 2. Cài đặt thủ công (nếu không dùng file bấm đúp)

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Chỉ cần `python-docx` (và `Flask` nếu dùng web UI). Không cần LibreOffice,
không cần Microsoft Word, không cần Node.

## 3. Chạy bằng dòng lệnh (CLI)

```bash
# sinh 5 biên bản từ dữ liệu mẫu E-GREEN 01/11/2026
./.venv/bin/python -m bienban fill samples/e-green-01112026.json -o output

# kiểm tra JSON trước khi điền (bắt lỗi ngày sai, thiếu số máy, dấu . thay vì ,)
./.venv/bin/python -m bienban check data.json

# in khung JSON rỗng để điền tay
./.venv/bin/python -m bienban template -o data.json

## 4. Web UI (ảnh → AI đọc → **sửa** → xem trước → tải file)

```bash
# có API key Gemini trên server (khuyến nghị)
export GEMINI_API_KEY="AIza..."
./.venv/bin/python web/app.py          # http://127.0.0.1:8000

# hoặc không đặt gì: dán key vào ô “API key Gemini” trên giao diện
./.venv/bin/python web/app.py
PORT=8080 ./.venv/bin/python web/app.py
```

### 4.1. Giao diện: 3 bước, sáng, theo bộ nhận diện công ty

Thanh trên cùng mang **logo thật lấy từ file mẫu Word** (không phải ảnh chép
tay, nên đổi logo công ty là giao diện đổi theo), màu xanh `#241a63` + đỏ
`#d81f26` đúng hai màu trong logo. Dưới đó là thanh **3 bước** luôn hiện để biết
mình đang ở đâu:

```
1 Chọn ảnh  →  2 Soát & sửa dữ liệu  →  3 Xem trước & tải Word
```

Các tiện ích khi dùng thật ngoài hiện trường:

* nút **A+** phóng to toàn bộ chữ và ô nhập (nhớ lựa chọn cho lần sau);
* nút **🖨 In / PDF** in bản xem trước đang mở (hoặc mở tab riêng);
* mọi ô nhập đều có nhãn (đọc được bằng trình đọc màn hình), tab/nút bấm được
  bằng bàn phím, đóng hộp thoại bằng `Esc`;
* màu chữ đạt chuẩn tương phản WCAG AA trên nền sáng.

### 4.2. Ba bước trên giao diện

**Bước 1 – Ảnh.** Kéo–thả hoặc bấm chọn ảnh chụp biên bản viết tay (JPG/PNG,
tối đa 24 ảnh/lần). Ảnh được thu nhỏ còn cạnh dài 2000 px ngay trên server
trước khi gửi Google (nhanh, rẻ, vẫn đủ nét đọc chữ tay).

**Bước 2 – Nhận dạng.** Chọn model rồi bấm **“✨ Nhận dạng ảnh → điền form”**.
Server gọi Gemini (`generateContent`, `responseMimeType: application/json`,
`temperature 0.1`) rồi **chuẩn hoá** kết quả về đúng JSON của tool. Mọi ô hiện
ra trong form để soát:

* ô chữ / số / ngày / ô chọn (Lý do kiểm định, Kết quả, Vật liệu… **vẫn gõ
  được giá trị ngoài danh sách**);
* dãy số (5 nấc tỉ số biến áp, R một chiều) tách thành **từng ô một nấc** —
  không phải gõ dãy ngăn bằng dấu phẩy (dấu phẩy trong tiếng Việt là dấu thập
  phân, gõ dãy sẽ sai);
* bảng kết quả (MCCB / LA / FCO / điện trở nối đất): **+ Thêm dòng**, **✕ Xoá
  dòng**; sửa dòng thì `Số lượng` tự cập nhật (`01`, `02`…);
* thanh ghi chú hiện `ai_notes` — những chỗ AI **không chắc** (số mờ, chữ bị
  sửa…) để người dùng kiểm tra trước;
* nút **“+ Thêm biên bản khác”** nếu ảnh thiếu một tờ (thêm mẫu 46 khi AI chỉ
  đọc ra 44/45…).

**Bước 3 – Xem trước & tải.** Bấm **“Xem trước & sinh biên bản”** là thấy ngay
**bản in** đúng như file Word sẽ xuất ra (logo, bảng SỐ/NGÀY, đánh số I/II/III,
bảng kẻ gộp ô, số liệu, chữ ký, footer) — soát xong mới tải:

* tab **44 … 48** chuyển nhanh giữa các biên bản
* **⬇ Tải** từng file, **⬇ Tải tất cả (.zip)**, **Tab riêng** để in ra PDF

> Vì sao tải bằng link `/download/<token>/<file>` chứ không phải blob: trong
> iframe preview (Arena, Zalo, Facebook…) nhiều trình duyệt chặn tải file sinh
> ra bằng `URL.createObjectURL`. Link GET thật thì luôn tải được. File được
> lưu tạm 6 giờ rồi tự dọn.

### 4.3. API key — không bao giờ gửi xuống trình duyệt

| Cách | Ưu điểm |
|---|---|
| `GEMINI_API_KEY` trong biến môi trường | key không rời khỏi server, người dùng không phải nhập |
| Dán vào ô “API key Gemini” | dùng nhanh khi chưa muốn cấu hình server; key chỉ đi theo header `X-Gemini-Key`, **không ghi log, không lưu ổ đĩa**, và được lưu trong `localStorage` để lần sau khỏi nhập lại |

Prompt gửi Gemini **hiện trên giao diện** (nút “Xem prompt gửi AI”) và sinh
tự động từ `bienban/schema.py`, nên danh sách khoá/nhãn trong prompt luôn
trùng với form trên màn hình và với mẫu Word. Xem bản đầy đủ:
`prompts/gemini.md` (hoặc `GET /api/ai/prompt?forms=45`).

Model: bấm **“↻ Lấy danh sách model”** để lấy các model đang hỗ trợ
`generateContent` từ chính API key của bạn. Model mặc định đặt bằng
`GEMINI_MODEL` (mặc định `gemini-2.5-flash`); tên model cũ đã bị khai tử
(`gemini-1.*`, `gemini-3.5-flash`…) được tự chuyển về mặc định.

### 4.4. API (dùng từ script cũng được)

| Endpoint | Việc |
|---|---|
| `GET /api/ai/schema` | cấu trúc form (nhóm, ô, bảng) để dựng UI khác |
| `GET /api/ai/status` | đã có key trên server chưa (không trả key) |
| `GET /api/ai/models` | danh sách model khả dụng |
| `GET /api/ai/prompt?forms=44,45` | prompt thật sẽ gửi Gemini |
| `POST /api/ai/recognize` | `multipart/form-data`: `images` (nhiều ảnh), `model`, `forms` → `{ok, data, notes, blocks, problems}` |
| `POST /api/normalize` | JSON bất kỳ → JSON chuẩn của tool (dùng cho dữ liệu cũ) |
| `POST /api/validate` | kiểm tra dữ liệu trước khi in |
| `POST /api/render` | sinh biên bản → `{token, files, previews, zip_url}` |
| `GET /download/<token>/<file>` · `/preview/<token>/<file>` | tải / xem trước |

`data` trả về từ `/api/ai/recognize` dùng được ngay cho `/api/render`:

```bash
curl -s -X POST http://127.0.0.1:8000/api/ai/recognize \
     -H "X-Gemini-Key: $GEMINI_API_KEY" \
     -F images=@anh1.jpg -F images=@anh2.jpg -F forms=44,45 -F model=gemini-2.5-flash \
  | python -c "import json,sys; json.dump(json.load(sys.stdin)['data'], open('data.json','w'), ensure_ascii=False)"
./.venv/bin/python -m bienban fill data.json -o output
```

### 4.5. Xem trước bằng Python

Hàm dựng bản xem trước dùng lại được ở nơi khác:

```python
from bienban.preview import docx_to_html
html = docx_to_html("output/45_50451126BBTC.docx")   # khối HTML + logo base64
```

## 5. JSON đầu vào

Xem `samples/e-green-01112026.json` (dữ liệu thật từ 7 ảnh biên bản viết tay +
1 ảnh công tơ). Prompt để LLM đọc ảnh xuất ra đúng cấu trúc này nằm trong
`prompts/extract.md` (bản viết tay, để đọc hiểu) và được **sinh tự động** từ
`bienban/schema.py` ở `prompts/gemini.md` (bản thật sự gửi đi — sửa schema là
prompt đổi theo, không bị lệch form).

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

## 6. Cấu hình (tuỳ chọn)

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

## 7. Cách hoạt động

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

## 8. Mẫu 44 (.doc cũ)

`44 BB MBA 1P 50KVA.doc` là Word 97. Để điền form đồng nhất, mẫu 44 đã được
dựng lại thành `templates/44 BB MBA 1P.docx` bằng `tools/build_template_44.py`:
nhân bản khung (style, 3 header logo, footer, khổ giấy, lề) của `45 MCCB 250A.docx`
rồi chép nguyên nội dung bản .doc (đúng thứ tự mục I → V, đúng nhãn, đúng đơn vị).

```bash
./.venv/bin/python tools/build_template_44.py
```

Bản .doc gốc được giữ tại `legacy/44 BB MBA 1P 50KVA.doc` để đối chiếu.

## 9. Kiểm thử

```bash
./.venv/bin/python -m pytest -q      # 91 test
```

Không cần cài gì thêm — test Gemini dùng stub, test launcher tự bật server ở
cổng ngẫu nhiên rồi tắt.

Bao gồm: chuẩn hoá ngày/số, nhận dạng nhãn, nội dung từng biên bản 44–48,
giữ header/footer + ảnh logo, chế độ in đậm/in hoa, validate dữ liệu, dựng bản
xem trước HTML (logo, gộp ô, số liệu), API web (render / download / preview),
**nhận dạng ảnh Gemini** (prompt, gọi API, parse JSON, chuẩn hoá dữ liệu AI trả
về, endpoint `/api/ai/*`), **bảng nhiều dòng** (`rows[]` → Word: thêm/bớt dòng
cho 45/46/47/48), **giao diện** (logo lấy từ mẫu Word, CSS thương hiệu, mọi ô
của 5 mẫu đều sửa được, chữ lớn, in ấn) và **bộ khởi động** (`launcher.py`,
`.bat`/`.command`/`.sh`: tự cài môi trường, hỏi key 1 lần, tự mở trình duyệt,
tự nhảy cổng khi bận).

Kiểm thử Gemini **không** gọi mạng thật: `vision._request` được thay bằng hàm
giả lập, nên chạy offline vẫn đủ và không tốn quota.

## 10. Cấu trúc thư mục

```
bienban/            # thư viện chính
  normalize.py      #   chuẩn hoá ngày, số, đọc số thành chữ
  spec.py           #   "hợp đồng dữ liệu": nhãn ↔ đường dẫn JSON cho từng mẫu
  labels.py         #   điền ô "Nhãn: giá trị"
  ooxml.py          #   thao tác XML Word (giữ định dạng gốc)
  fill.py           #   điều phối + điền bảng + chữ ký + kết luận
  validate.py       #   kiểm tra JSON trước khi điền
  preview.py        #   dựng bản xem trước HTML từ file .docx
  schema.py         #   đặc tả ô sửa được + bảng (dùng cho UI và prompt AI)
  vision.py         #   Gemini: prompt, gọi API, chuẩn hoá JSON trả về
  __main__.py       #   CLI (fill / check / template / forms)
templates/          # 5 mẫu Word đang dùng
legacy/             # bản .doc gốc của mẫu 44
samples/            # JSON mẫu (dữ liệu thật E-GREEN 01/11/2026)
prompts/extract.md  # prompt trích xuất ảnh → JSON (bản viết tay, để đọc)
prompts/gemini.md   # prompt THẬT gửi Gemini (sinh từ schema.py)
tools/              # script dựng lại mẫu 44
web/                # Flask UI
  static/app.css    #   giao diện (bộ nhận diện, chữ lớn, in ấn)
tests/              # pytest
output/             # file .docx sinh ra (đã .gitignore)
```

## 11. Mở rộng

* **Thêm mẫu mới**: thêm file vào `templates/`, khai báo `TEMPLATES`, `TITLES`,
  `DATA_KEYS`, `LABELS` trong `bienban/spec.py` (và `TABLE_PROBES` nếu có bảng).
* **Đổi nhãn trong mẫu Word**: sửa `LABELS` — không cần chạm vào code điền.
* **Đổi định dạng in**: sửa `config.json` mục `style`.
