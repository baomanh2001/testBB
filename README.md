# Hệ thống Đọc Ảnh Biên Bản Hiện Trường & Xuất Word (.docx) — Toàn Cầu

Ứng dụng Web chuyên dụng cho **Công ty CP Thí nghiệm điện Toàn Cầu** giúp chuyển tự động **ảnh chụp biên bản viết tay tại hiện trường** (kèm ảnh phụ trợ như công tơ điện, nhãn máy, biển tên trạm) sang bộ **file Word (`.docx`) theo biểu mẫu công ty** (giữ nguyên logo, watermark chìm, bảng biểu, đánh số La Mã, footer và chữ ký nhúng).

---

## 1. Các mẫu biên bản đã tích hợp sẵn

1. **Máy biến áp 1 pha (`MBA 1P`)** — Tự động gộp ảnh Trang 1/2 + Trang 2/2 thành 1 file `.docx` chuẩn 2 trang (có đánh số `Trang 1/2`, `Trang 2/2`), hỗ trợ linh hoạt 3 nấc / 5 nấc phân áp và tính nhanh hệ số hấp thụ $K_{ht} = R_{60''} / R_{15''}$.
2. **Máy cắt hạ thế (`MCCB`)** — Hỗ trợ 1 hoặc nhiều máy cắt trong bảng kết quả.
3. **Chống sét van (`LA`)** — Tự động đổi đơn vị MCOV (ví dụ `15300V` → `15,3kV`), hỗ trợ nhiều LA (`LA 01`, `LA 02`, `LA 03`...).
4. **Cầu chì tự rơi (`FCO`)** — Tự động nhận diện giá trị sửa tay trên giấy, hỗ trợ nhiều FCO.
5. **Điện trở nối đất (`ĐTNĐ`)** — Đúng tiêu đề *BIÊN BẢN THỬ NGHIỆM*, hỗ trợ nhiều điểm đo tiếp địa.

6. **Máy biến áp 3 pha (`MBA 3P`)** — bảng cách điện, điện trở và tỉ số biến theo nấc.
7. **Máy cắt hạ thế (`ACB`)**.
8. **Cầu chì tự rơi có dập hồ quang (`LBFCO`)**.
9. **Thông tuyến cáp ngầm trung thế**.
10. **Tủ tụ bù hạ thế** — các bảng MCCB tổng, nhánh, contactor và tụ.

Hai bộ dữ liệu mẫu có thể chọn trên giao diện: Dream Mekong 1500kVA (7 biên bản) và E-GREEN 50kVA (5 biên bản). Bản xem trước được dựng từ file Word xuất ra; trình duyệt có thể phân trang hoặc hiển thị phông chữ khác Microsoft Word, vì vậy cần kiểm tra file Word trước khi sử dụng. AI có thể đọc sai hoặc bỏ sót: luôn đối chiếu ảnh gốc, số liệu và chữ ký trước khi phát hành.

---

## 2. Tính năng nổi bật

- **Hỗ trợ kép AI Vision**: Chọn linh hoạt **Google Gemini** (`gemini-3.8-flash` mặc định; có thể chọn hoặc nhập model khác tùy quyền truy cập API) hoặc **OpenAI** (`gpt-4o`, `gpt-4.1`), kèm chế độ nhập/chỉnh sửa trực tiếp không cần key.
- **Đối chiếu Song song (Split-Screen)**: Bên trái là trình soi ảnh gốc (phóng to/thu nhỏ lăn chuột, kéo giữ, xoay trái/phải 90°), bên phải là Form chỉnh sửa số liệu & **Xem trước nội dung file Word**.
- **Đồng bộ cả lô Trạm biến áp**: Chỉnh 1 lần *Tên công trình, Địa chỉ, Đơn vị yêu cầu, Ngày kiểm định, Ngày phát hành, STT bắt đầu (`44, 45...`), Bộ 3 người ký & Chữ ký ảnh* → áp dụng tự động cho toàn bộ biên bản trong trạm.
- **Tải lẻ `.docx` hoặc Tải trọn bộ `.zip`**: Xuất trực tiếp chuẩn `.docx` mở mượt trên mọi phiên bản Microsoft Word.

---

## 3. Cách chạy trên máy tính cá nhân

### Trên Windows
Nhấp đúp vào file **`run.bat`** (hệ thống tự tạo môi trường Python `.venv`, cài thư viện và mở trình duyệt tại `http://localhost:8000`).

### Trên Linux / macOS
```bash
chmod +x run.sh
./run.sh
```

---

## 4. Lấy API Key miễn phí để đọc chữ viết tay tự động

- **Google Gemini (Khuyên dùng)**: Truy cập [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → Bấm **Create API Key** → Dán vào nút **Cấu hình AI Key** trên góc phải giao diện web.
- **OpenAI**: Dùng API Key `sk-...` từ tài khoản OpenAI Platform của bạn.

---

## 5. Cấu trúc mã nguồn (Dễ dàng mở rộng thêm mẫu mới)

- `app/templates/`: Chứa các file `.docx` mẫu chuẩn gốc của Toàn Cầu.
- `app/schemas.py`: Khai báo cấu trúc trường dữ liệu cho từng loại biên bản.
- `app/docx_generator.py`: Bộ xuất file `.docx` giữ nguyên định dạng XML, bảng biểu, logo, watermark và chữ ký.
- `app/static/vision_ai.js`: Prompt chuyên ngành thí nghiệm điện & kết nối Gemini / OpenAI Vision.
- `app/static/index.html`, `styles.css`, `app.js`: Giao diện Web đối chiếu ảnh – sửa form – xem trước A4.

- `app/static/vendor/`: Thư viện JSZip và docx-preview cùng giấy phép, dùng để dựng bản xem trước từ file Word xuất ra.

### Cấu trúc và số thứ tự trong Word

Tiêu đề, dấu đầu dòng và số thứ tự được ghi trực tiếp vào nội dung Word theo thứ tự từng mẫu; nhờ vậy chúng cũng hiện trong bản xem trước và không phụ thuộc vào bộ đánh số tự động của trình đọc Word. Khi tự thêm, xóa hoặc đổi thứ tự mục trong Word, cần chỉnh lại các số này thủ công. Ví dụ mẫu LBFCO trong PDF gốc dùng I–III cho phần công trình/thông số/kết quả và IV–VI cho tiêu chuẩn/thiết bị/kết luận.
