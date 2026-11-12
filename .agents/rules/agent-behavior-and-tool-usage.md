# Quy Tắc Hành Vi & Sử Dụng Công Cụ Của Agent (Production Engineering Workflow)

Tài liệu này định hình các quy tắc ứng xử, thao tác công cụ và chuẩn mực kỹ thuật cho AI Agent trong quá trình phát triển và vận hành sản phẩm **EcomReview AI**.

---

## 1. Phong Cách Giao Tiếp & Phản Hồi Kỹ Thuật
- **Đúng trọng tâm & Thực tế**: Trả lời trực diện vào giải pháp kỹ thuật, hiệu năng hệ thống và trải nghiệm người dùng cuối; không trình bày lý thuyết rườm rà khi không được yêu cầu.
- **Ngôn ngữ phản hồi**: Mặc định giao tiếp với người dùng bằng **tiếng Việt** chuẩn xác, chuyên nghiệp.
- **Quy chuẩn mã nguồn**:
  - Mã nguồn Python (Backend/AI Engine): Tên class, hàm, biến, comment và docstrings viết bằng **tiếng Anh** chuẩn quốc tế (tuân thủ PEP 8 và Google Python Style Guide).
  - Mã nguồn JavaScript/JSX (React Frontend): Tuân thủ chuẩn ES6+, đặt tên component theo `PascalCase`, biến/hàm theo `camelCase`, giao diện hiển thị cho người dùng cuối bằng tiếng Việt tự nhiên, rõ ràng.
- **Quy tắc đặt tên commit Git khi push GitHub:**
  - *Nếu người dùng yêu cầu Agent tự tạo tên commit:* Bắt buộc viết bằng **tiếng Việt**, **không** dùng dạng tiền tố `abc: xyz` (chỉ viết trực tiếp nội dung `xyz`, ví dụ: `nâng cấp bộ lọc bảo mật API và tối ưu giao diện quản lý phản hồi CSKH`).
  - *Nếu người dùng tự đặt tên:* Lấy chính xác 100% nguyên văn tên người dùng đặt (không tự ý chỉnh sửa).

---

## 2. Kỷ Cương Phẫu Thuật Tối Thiểu (Minimal Diff & API Contract Protection)
- **Phong cách lập trình bảo thủ (Conservative & Surgical):** Chỉ sửa đúng các dòng mã nguồn cần thiết để hoàn thành mục tiêu. Giữ nguyên hiện trạng các module đang chạy ổn định.
- **Bảo vệ hợp đồng giao tiếp (API Contract Integrity):** Khi chỉnh sửa các endpoint trong `src/ecomreview/api/main.py` hoặc schema trong `src/ecomreview/schemas.py`, bắt buộc kiểm tra tính tương thích ngược với `frontend/src/api/client.js` và các bài kiểm thử API.
- **Tuyệt đối cấm Over-engineering:** Không tự ý đổi tên biến, không tự ý refactor các hàm lân cận, không viết lại cả cụm code đang hoạt động tốt.

---

## 3. Quy Trình Plan Gate 2 Bước (Chống Nhảy Bổ Vào Viết Code)
- **Bước 1 (Lock):** Khi nhận yêu cầu tính năng mới hoặc xử lý lỗi phức tạp, trước tiên phải phân tích luồng code, xác định danh sách file bị ảnh hưởng, vạch ra các edge cases trong môi trường Production và phác thảo giải pháp Minimal Diff. **CHƯA ĐƯỢC CHỈNH SỬA MÃ NGUỒN** khi kế hoạch chưa rõ ràng hoặc chưa đạt đồng thuận.
- **Bước 2 (Unlock & Execute):** Sau khi kế hoạch được xác định, tiến hành thực thi chuẩn xác theo đúng phạm vi đã định, không đi chệch hướng.

---

## 4. Chiến Lược Quản Trị Ngữ Cảnh & Điều Phối Sub-Agent (Context Hygiene)
- **Tránh ngộ độc ngữ cảnh:** Khi đọc các file code hoặc tài liệu trên 50 dòng, luôn sử dụng `StartLine` và `EndLine` để chỉ nạp vùng nội dung cần xử lý.
- **Định vị chính xác trước khi đọc:** Sử dụng `run_command` (`Select-String` / `grep`) để xác định dòng cụ thể cần chỉnh sửa.
- **Ủy quyền cho Sub-agent chuyên biệt:**
  - Khi cần khảo sát diện rộng (đọc > 3 file lớn hoặc truy vết luồng dữ liệu E2E từ Database $\rightarrow$ Backend $\rightarrow$ Frontend), triệu hồi Sub-agent `codebase-explorer`.
  - Trước khi commit hoặc hoàn tất cụm tính năng lớn, triệu hồi Sub-agent `critic-reviewer` để soi `git diff` và phản biện độc lập.

---

## 5. Thao Tác Chỉnh Sửa Mã Nguồn An Toàn
- **Ưu tiên công cụ chuyên dụng**:
  - Đọc file: `read_file` (kèm `StartLine` và `EndLine`).
  - Sửa file: `edit_file` với đoạn `Target` chuẩn xác từng ký tự và thụt lề (indentation).
  - Tạo file mới: `write_file`.
- **Không dùng shell để ghi đè code**: Tránh dùng lệnh shell (`echo`, `Set-Content`, `sed`) để sửa mã nguồn nhằm ngăn ngừa lỗi hỏng bảng mã UTF-8 tiếng Việt hoặc lỗi xuống dòng CRLF/LF.
- Lệnh shell (`run_command`) chỉ được dùng cho:
  - Quản lý môi trường và thư viện: `pip install`, `npm install`, `npm run build`.
  - Chạy kiểm thử tự động: `.venv\Scripts\pytest -v`.
  - Kiểm tra lint & format: `.venv\Scripts\python -m ruff check .`, `.venv\Scripts\python -m ruff format . --check`.
  - Vận hành dịch vụ, Git và Docker: `git`, `docker compose`, `uvicorn`.

---

## 6. Kiểm Thử & Kiểm Chứng Thực Nghiệm (Verification-Driven Development - VDD)
- Tuyệt đối không phán đoán hoặc giả định rằng code "chắc chắn đã chạy đúng".
- Khi thêm mới một chức năng hoặc sửa lỗi, bắt buộc bổ sung hoặc cập nhật bài kiểm thử tự động trong `tests/`.
- Chạy toàn bộ bộ kiểm thử trước khi thông báo hoàn thành bất kỳ công việc nào:
  ```powershell
  .venv\Scripts\pytest -v
  .venv\Scripts\python -m ruff check .
  .venv\Scripts\python -m ruff format . --check
  ```
- Tuyệt đối không để test bị gãy (`FAILED`) hoặc còn lỗi linter/formatter khi bàn giao.

---

## 7. Quy Định Bản Quyền Bắt Buộc (Credit Note)
Mọi file mã nguồn mới hoặc file cấu hình/tài liệu được tạo ra hoặc cập nhật trong dự án bắt buộc phải có dòng ghi chú tác quyền ở cuối file:
- Đối với file Python (`.py`), Shell (`.sh`, `.ps1`), YAML (`.yaml`, `.yml`):
  ```python
  # CreBy: MenBoyBMN
  ```
- Đối với file Markdown (`.md`), HTML (`.html`):
  ```markdown
  <!-- CreBy: MenBoyBMN -->
  ```

<!-- CreBy: MenBoyBMN -->
