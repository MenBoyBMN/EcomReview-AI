# Quy Tắc Tác Chiến Kỷ Cương & Tối Ưu Hóa Antigravity (AGY Rules)

Tài liệu này là quy tắc hành vi bắt buộc dành cho Antigravity (Gemini Engine) nhằm duy trì phong cách lập trình **Bảo thủ & Phẫu thuật (Conservative & Surgical)**, triệt tiêu hoàn toàn 5 điểm yếu mặc định của mô hình và tối ưu hóa năng lực triển khai dự án **EcomReview AI**.

---

## 1. Kỷ Cương Phẫu Thuật Tối Thiểu (Minimal Diff Protocol)

- **Mục tiêu:** Sửa đúng điểm lỗi hoặc bổ sung đúng chức năng được giao; giảm thiểu tối đa rủi ro gây lỗi dây chuyền (regression bugs).
- **Quy tắc bất biến:**
  1. Chỉ chạm vào các dòng code, hàm số hoặc file liên quan trực tiếp đến yêu cầu.
  2. Tuyệt đối **không** tự ý đổi tên biến, sắp xếp lại thứ tự các hàm, format lại cả file hoặc tái cấu trúc (refactor) các đoạn code lân cận nếu người dùng không yêu cầu.
  3. Tuyệt đối **không** tự ý cài thêm thư viện phụ thuộc mới (`pip install`) khi chưa kiểm tra thư viện đã có trong `requirements.txt` hoặc chưa được người dùng phê duyệt.
  4. Sử dụng công cụ `edit_file` với đoạn `Target` chuẩn xác từng ký tự, giữ nguyên khoảng trắng và mức thụt dòng (indentation). Tránh ghi đè (`write_file`) toàn bộ file mã nguồn lớn.

---

## 2. Quy Trình Plan Gate 2 Bước (Chống Nhảy Bổ Vào Viết Code)

Đối với mọi yêu cầu thêm tính năng (feature) hoặc sửa lỗi khó (complex bug):

- **Bước 1: Khóa Tay & Lập Kế Hoạch (Lock / Analysis Gate):**
  - Định vị chính xác các file liên quan bằng công cụ tìm kiếm hoặc ủy quyền cho Sub-agent.
  - Trình bày bản kế hoạch ngắn gọn (5–10 dòng):
    - Các file và hàm sẽ can thiệp.
    - Logic thay đổi phẫu thuật (Minimal Diff).
    - Các trường hợp biên (edge cases) và giải pháp xử lý.
  - **CHƯA ĐƯỢC CHỈNH SỬA CODE** ở bước này khi kế hoạch chưa rõ ràng hoặc người dùng yêu cầu xem trước.
- **Bước 2: Mở Khóa & Thực Thi (Unlock & Execute):**
  - Chỉ can thiệp mã nguồn khi kế hoạch đã được chốt.
  - Thực hiện đúng theo phạm vi đã vạch ra, không tự ý mở rộng phạm vi (Scope Creep).

---

## 3. Vệ Sinh Ngữ Cảnh (Context Hygiene & Call Graph Navigation)

- **Tránh ngộ độc ngữ cảnh:** Dù Gemini có context window lớn (1M–2M tokens), việc nạp 30–40 file lớn vào cùng một phiên chat sẽ làm suy giảm độ chính xác logic.
- **Nguyên tắc đọc file:**
  - Định vị dòng trước bằng `run_command` (grep / Select-String) hoặc phân tích sơ đồ gọi hàm (Call Graph).
  - Luôn sử dụng `StartLine` và `EndLine` khi đọc các file lớn để chỉ nạp đúng phân đoạn cần xử lý.
- **Ủy quyền cho Sub-agent:**
  - Khi cần khảo sát kiến trúc hoặc truy vết luồng dữ liệu diện rộng, triệu hồi Sub-agent `codebase-explorer`. Sub-agent sẽ đọc hàng chục file trong không gian cô lập của nó và chỉ trả về bản tóm tắt tinh gọn cho Main Agent.

---

## 4. Cơ Chế Phản Biện Chéo Độc Lập (Adversarial Critic Gate)

- **Chống thiên kiến tự xác nhận:** Main Agent không tự đánh giá code mình vừa viết là hoàn hảo.
- **Nghiệm thu qua `critic-reviewer`:**
  - Trước khi commit hoặc bàn giao một cụm chức năng quan trọng, triệu hồi Sub-agent `critic-reviewer`.
  - Sub-agent này chạy độc lập, soi chiếu toàn bộ `git diff` để phát hiện:
    - Rủi ro Null Reference, unhandled exceptions.
    - Truy vấn SQL N+1 hoặc thiếu index.
    - Vi phạm kiểu dữ liệu Pydantic schemas.
    - Vi phạm 7 luật xác định (R1–R7) trong tri thức miền áo mưa.

---

## 5. Kiểm Chứng Thực Nghiệm Bắt Buộc (Verification-Driven Development - VDD)

- Tuyệt đối không dừng lại ở mức "nhìn code trông có vẻ đúng".
- Mọi thay đổi mã nguồn phải được chứng minh bằng lệnh kiểm chứng thực tế trên Terminal trước khi báo cáo hoàn tất:
  ```powershell
  # 1. Kiểm tra toàn bộ unit & integration tests
  .venv\Scripts\pytest -v

  # 2. Kiểm tra chất lượng và định dạng mã nguồn PEP 8
  .venv\Scripts\python -m ruff check .
  .venv\Scripts\python -m ruff format . --check
  ```
- Nếu kiểm thử hoặc lint thất bại, bắt buộc phân tích nguyên nhân gốc rễ và sửa chữa ngay lập tức; không bàn giao mã nguồn khi còn lỗi.

---

## 6. Tuân Thủ Bản Quyền Dự Án (Credit Note)

- Mọi file mới hoặc sửa đổi có ý nghĩa phải có chữ ký tác quyền ở cuối:
  - File Python, Shell, YAML: `# CreBy: MenBoyBMN`
  - File Markdown, HTML: `<!-- CreBy: MenBoyBMN -->`

<!-- CreBy: MenBoyBMN -->
