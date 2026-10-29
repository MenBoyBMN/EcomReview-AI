# Quy Tắc Hành Vi & Sử Dụng Tool Của Agent

Tài liệu này định hình các quy tắc ứng xử, thao tác công cụ và chuẩn mực code cho AI Agent trong dự án **EcomReview AI**.

---

## 1. Phong Cách Giao Tiếp & Phản Hồi
- **Đúng trọng tâm & Ngắn gọn**: Trả lời trực diện, súc tích, không lặp lại nguyên văn các chỉ thị hoặc tóm tắt dài dòng khi không được yêu cầu.
- **Ngôn ngữ phản hồi**: Mặc định giao tiếp với người dùng bằng **tiếng Việt**, trừ khi người dùng yêu cầu ngôn ngữ khác.
- **Quy chuẩn mã nguồn**: Toàn bộ mã nguồn Python, tên class, hàm, biến, comment trong code, docstrings, và commit messages bắt buộc viết bằng **tiếng Anh** chuẩn quốc tế (tuân thủ PEP 8 và Google Python Style Guide).

---

## 2. Chiến Lược Đọc File Có Phạm Vi (Context Optimization)
- **Tránh đọc toàn bộ file lớn**: Khi đọc các file code hoặc tài liệu trên 50 dòng, luôn sử dụng `StartLine` và `EndLine` (hoặc offset/limit) để chỉ nạp vùng nội dung cần xử lý.
- **Định vị chính xác trước khi đọc**: Sử dụng `run_command` (grep / Select-String) hoặc tìm kiếm theo từ khóa để xác định dòng cụ thể cần chỉnh sửa.

---

## 3. Thao Tác Chỉnh Sửa Mã Nguồn An Toàn
- **Ưu tiên công cụ chuyên dụng**:
  - Đọc file: `read_file`.
  - Sửa file: `edit_file` với đoạn `Target` chuẩn xác từng ký tự và thụt lề (indentation).
  - Tạo file mới: `write_file`.
- **Không dùng shell bừa bãi**: Tránh dùng `powershell`, `sed`, `awk` hoặc `echo` đè file gây lỗi mã hóa UTF-8 tiếng Việt.
- Lệnh shell (`run_command`) chỉ được dùng cho:
  - Khởi tạo môi trường ảo, cài đặt gói: `pip install`, `python -m venv`.
  - Chạy kiểm thử tự động: `pytest`.
  - Kiểm tra lint & format: `ruff check`, `ruff format`.
  - Thao tác Git và Docker: `git`, `docker compose`.

---

## 4. Kiểm Thử & Đảm Bảo Tính Toàn Vẹn Của Hệ Thống
- Khi thêm mới một chức năng hoặc sửa lỗi, bắt buộc viết kèm bài test trong `tests/`.
- Chạy `pytest` trước khi thông báo hoàn thành bất kỳ task nào. Tuyệt đối không để test bị gãy (`FAILED`).
- Giữ sạch sẽ môi trường phát triển, không ghi file rác vào thư mục gốc dự án.

---

## 5. Quy Định Bản Quyền Bắt Buộc (Credit Note)
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
