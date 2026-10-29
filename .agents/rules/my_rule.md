# Quy Định Bổ Sung Dành Cho Agent (User Rules & Operational Parameters)

Tài liệu lưu trữ các quy định chỉ đạo và tham số vận hành đặc biệt từ người dùng dành cho Antigravity (Gemini Engine) trong quá trình phát triển **EcomReview AI**.

---

## 1. Thiết Lập Phong Cách Làm Việc (Operating Persona)
- **Phong cách cốt lõi:** **Bảo thủ & Phẫu thuật (Conservative & Surgical)**.
- **Mục tiêu:** Khắc phục triệt để các hạn chế mặc định của Gemini (Over-engineering, ngộ độc ngữ cảnh, nhảy vào code khi chưa hiểu, thiên kiến tự khen, và ảo giác khi kiểm thử).
- **Tiêu chuẩn chất lượng:** Chất lượng code, độ chính xác phẫu thuật và mức độ hiểu ý đạt hoặc vượt chuẩn Claude Code.

---

## 2. Các Quy Định Bắt Buộc Trong Mọi Phiên Làm Việc
1. **Khóa phạm vi (Minimal Diff):** Chỉ sửa đúng dòng lỗi hoặc đúng chức năng được giao. Không tự ý refactor hay thay đổi bất kỳ thành phần nào khác.
2. **Quy trình Plan Gate:** Luôn phân tích phạm vi file và tóm tắt kế hoạch trước khi chỉnh sửa mã nguồn phức tạp.
3. **Bảo vệ ngữ cảnh:** Ủy quyền việc đọc code diện rộng (> 3 file) cho Sub-agent `codebase-explorer`.
4. **Phản biện độc lập:** Sử dụng Sub-agent `critic-reviewer` để soi chiếu `git diff` trước khi commit hoặc bàn giao.
5. **Kiểm chứng thực nghiệm (VDD):** Luôn tự chạy `.venv\Scripts\pytest -v` và `.venv\Scripts\python -m ruff check .` để chứng minh code hoạt động 100%.

<!-- CreBy: MenBoyBMN -->
