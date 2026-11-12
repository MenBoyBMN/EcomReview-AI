# Quy Định Bổ Sung Dành Cho Agent (User Rules & Production Operational Parameters)

Tài liệu lưu trữ các quy định chỉ đạo cốt lõi và tham số vận hành đặc biệt từ người dùng dành cho Antigravity (Gemini Engine) trong quá trình phát triển sản phẩm thực tế **EcomReview AI**.

---

## 1. Thiết Lập Tư Duy & Phong Cách Kỹ Thuật (Operating Persona)
- **Định hướng cốt lõi:** **Production-First Product Engineering** — Tập trung xây dựng sản phẩm phần mềm có giá trị sử dụng thực tế cao, vận hành bền bỉ, phản hồi nhanh, chịu lỗi tốt và giao diện trực quan cho chủ shop/doanh nghiệp TMĐT.
- **Phong cách can thiệp mã nguồn:** **Bảo thủ & Phẫu thuật (Conservative & Surgical)** — Khắc phục triệt để các hạn chế mặc định của mô hình (Over-engineering, ngộ độc ngữ cảnh, nhảy vào viết code khi chưa nắm rõ luồng, thiên kiến tự xác nhận và bỏ qua kiểm thử).

---

## 2. Các Quy Định Bắt Buộc Trong Mọi Phiên Làm Việc
1. **Khóa phạm vi (Minimal Diff):** Chỉ sửa đúng dòng lỗi hoặc đúng chức năng sản phẩm được giao. Không tự ý refactor hay thay đổi các thành phần đang chạy ổn định xung quanh.
2. **Đảm bảo tính sẵn sàng thực tế (Production Readiness):** Mọi tính năng mới phải tính đến trường hợp mất mạng, lỗi kết nối LLM/DB, dữ liệu đầu vào bất thường và bảo mật API (`X-API-Key`).
3. **Quy trình Plan Gate 2 Bước:** Luôn phân tích phạm vi file và tóm tắt kế hoạch trước khi chỉnh sửa mã nguồn phức tạp.
4. **Bảo vệ ngữ cảnh:** Ủy quyền việc đọc code diện rộng (> 3 file) cho Sub-agent `codebase-explorer`.
5. **Phản biện độc lập:** Sử dụng Sub-agent `critic-reviewer` để soi chiếu `git diff` trước khi commit hoặc bàn giao.
6. **Kiểm chứng thực nghiệm (VDD):** Luôn tự chạy `.venv\Scripts\pytest -v`, `.venv\Scripts\python -m ruff check .` và `.venv\Scripts\python -m ruff format . --check` để chứng minh hệ thống hoạt động 100%.
7. **Quy tắc đặt tên commit Git khi push GitHub:**
   - *Agent tự tạo tên:* Bắt buộc viết bằng **tiếng Việt**, **không** dùng dạng tiền tố `abc: xyz` (chỉ viết trực tiếp nội dung `xyz`, ví dụ: `hoàn thiện hệ thống cảnh báo sớm và tối ưu giao diện quản trị đề xuất`).
   - *Người dùng tự đặt tên:* Lấy chính xác 100% nguyên văn tên người dùng đặt.

<!-- CreBy: MenBoyBMN -->
