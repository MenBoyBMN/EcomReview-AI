# Quy Tắc Hành Vi & Sử Dụng Tool Của Agent

Tài liệu này định hình các quy tắc ứng xử, thao tác công cụ và chuẩn mực code cho AI Agent trong dự án **EcomReview AI**.

---

## 1. Phong Cách Giao Tiếp & Phản Hồi
- **Đúng trọng tâm & Ngắn gọn**: Trả lời trực diện, súc tích, không lặp lại nguyên văn các chỉ thị hoặc tóm tắt dài dòng khi không được yêu cầu.
- **Ngôn ngữ phản hồi**: Mặc định giao tiếp với người dùng bằng **tiếng Việt**, trừ khi người dùng yêu cầu ngôn ngữ khác.
- **Quy chuẩn mã nguồn**: Toàn bộ mã nguồn Python, tên class, hàm, biến, comment trong code, docstrings, và commit messages bắt buộc viết bằng **tiếng Anh** chuẩn quốc tế (tuân thủ PEP 8 và Google Python Style Guide).

---

## 2. Kỷ Cương Phẫu Thuật Tối Thiểu (Minimal Diff & Scope Control)
- **Phong cách lập trình bảo thủ (Conservative & Surgical):** Chỉ sửa đúng các dòng mã nguồn cần thiết để hoàn thành mục tiêu. Giữ nguyên hiện trạng xung quanh.
- **Tuyệt đối cấm Over-engineering:** Không tự ý đổi tên biến, không tự ý refactor các hàm lân cận, không viết lại cả cụm code theo sở thích cá nhân.
- **Giới hạn phạm vi (Scope Locking):** Luôn xác định rõ chữ ký hàm và logic cốt lõi cần can thiệp; không làm phát sinh thay đổi ngoài phạm vi được người dùng chỉ định.

---

## 3. Quy Trình Plan Gate 2 Bước (Chống Nhảy Bổ Vào Viết Code)
- **Bước 1 (Lock):** Khi nhận task mới hoặc xử lý bug khó, trước tiên phải phân tích luồng code, xác định danh sách file bị ảnh hưởng, vạch ra các edge cases và phác thảo giải pháp Minimal Diff. **CHƯA ĐƯỢC CHỈNH SỬA MÃ NGUỒN** khi kế hoạch chưa rõ ràng hoặc chưa đạt đồng thuận.
- **Bước 2 (Unlock & Execute):** Sau khi kế hoạch được xác định, tiến hành thực thi chuẩn xác theo đúng phạm vi đã định, không đi chệch hướng.

---

## 4. Chiến Lược Quản Trị Ngữ Cảnh & Điều Phối Sub-Agent (Context Hygiene)
- **Tránh ngộ độc ngữ cảnh:** Khi đọc các file code hoặc tài liệu trên 50 dòng, luôn sử dụng `StartLine` và `EndLine` (hoặc offset/limit) để chỉ nạp vùng nội dung cần xử lý.
- **Định vị chính xác trước khi đọc:** Sử dụng `run_command` (grep / Select-String) hoặc tìm kiếm theo từ khóa để xác định dòng cụ thể cần chỉnh sửa.
- **Ủy quyền cho Sub-agent chuyên biệt:**
  - Khi cần khảo sát diện rộng (đọc > 3 file lớn hoặc trace luồng dữ liệu E2E), triệu hồi Sub-agent `codebase-explorer` để khảo sát trong bộ nhớ riêng của nó và trả về tóm tắt ngắn gọn cho Main Agent.
  - Trước khi commit hoặc hoàn tất cụm tính năng lớn, triệu hồi Sub-agent `critic-reviewer` để soi `git diff` và phản biện độc lập.

---

## 5. Thao Tác Chỉnh Sửa Mã Nguồn An Toàn
- **Ưu tiên công cụ chuyên dụng**:
  - Đọc file: `read_file` (kèm StartLine/EndLine).
  - Sửa file: `edit_file` với đoạn `Target` chuẩn xác từng ký tự và thụt lề (indentation).
  - Tạo file mới: `write_file`.
- **Không dùng shell bừa bãi**: Tránh dùng `powershell`, `sed`, `awk` hoặc `echo` đè file gây lỗi mã hóa UTF-8 tiếng Việt.
- Lệnh shell (`run_command`) chỉ được dùng cho:
  - Khởi tạo môi trường ảo, cài đặt gói: `pip install`, `python -m venv`.
  - Chạy kiểm thử tự động: `.venv\Scripts\pytest -v`.
  - Kiểm tra lint & format: `.venv\Scripts\python -m ruff check .`, `.venv\Scripts\python -m ruff format . --check`.
  - Thao tác Git và Docker: `git`, `docker compose`.

---

## 6. Kiểm Thử & Kiểm Chứng Thực Nghiệm (Verification-Driven Development - VDD)
- Tuyệt đối không phán đoán hoặc giả định rằng code "chắc chắn đã chạy đúng".
- Khi thêm mới một chức năng hoặc sửa lỗi, bắt buộc viết kèm bài test trong `tests/`.
- Chạy toàn bộ kiểm thử trước khi thông báo hoàn thành bất kỳ task nào:
  ```powershell
  .venv\Scripts\pytest -v
  .venv\Scripts\python -m ruff check .
  .venv\Scripts\python -m ruff format . --check
  ```
- Tuyệt đối không để test bị gãy (`FAILED`) hoặc có lỗi linter/formatter.
- Giữ sạch sẽ môi trường phát triển, không ghi file rác vào thư mục gốc dự án.

---

## 7. Quy Định Bản Quyền Bắt Buộc (Credit Note)
Mọi file mã nguồn mới hoặc file cấu hình/tài liệu được tạo ra trong dự án, bắt buộc phải có dòng ghi chú credit ở cuối trang:
- Đối với file Python (`.py`), Shell (`.sh`, `.ps1`), YAML (`.yaml`, `.yml`):
  ```python
  # CreBy: MenBoyBMN
  ```
- Đối với file Markdown (`.md`), HTML (`.html`):
  ```markdown
  <!-- CreBy: MenBoyBMN -->
  ```

<!-- CreBy: MenBoyBMN -->
