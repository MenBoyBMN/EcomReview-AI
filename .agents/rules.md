# Quy Tắc Tác Chiến Kỷ Cương & Vận Hành Sản Phẩm Production (AGY Rules)

Tài liệu này là quy tắc hành vi bắt buộc dành cho Antigravity (Gemini Engine) nhằm duy trì phong cách kỹ thuật **Bảo thủ, Phẫu thuật & Chuẩn Production (Conservative, Surgical & Production-Grade)** trong dự án **EcomReview AI**.

---

## 1. Kỷ Cương Phẫu Thuật Tối Thiểu (Minimal Diff & Zero-Breakage Protocol)

- **Mục tiêu:** Sửa đúng điểm lỗi hoặc nâng cấp đúng tính năng sản phẩm được yêu cầu; đảm bảo tính ổn định tuyệt đối cho hệ thống đang vận hành (Zero Regression).
- **Quy tắc bất biến:**
  1. Chỉ can thiệp vào các dòng code, hàm số hoặc file liên quan trực tiếp đến yêu cầu công việc.
  2. Tuyệt đối **không** tự ý đổi tên biến, thay đổi chữ ký hàm (function signature), đổi cấu trúc JSON trả về của 15 REST API endpoints hoặc refactor các đoạn code lân cận nếu không được yêu cầu.
  3. Tuyệt đối **không** tự ý cài thêm thư viện phụ thuộc mới (`pip install` / `npm install`) khi chưa kiểm tra `requirements.txt` / `package.json` và chưa có sự đồng thuận của người dùng.
  4. Sử dụng công cụ `edit_file` với đoạn `Target` chuẩn xác từng ký tự, giữ nguyên khoảng trắng và mức thụt dòng (indentation). Tránh ghi đè (`write_file`) toàn bộ file mã nguồn lớn.

---

## 2. Quy Trình Plan Gate 2 Bước (Chống Nhảy Bổ Vào Viết Code)

Đối với mọi yêu cầu phát triển tính năng sản phẩm mới hoặc xử lý lỗi hệ thống phức tạp:

- **Bước 1: Khóa Tay & Lập Kế Hoạch (Lock / Analysis Gate):**
  - Định vị chính xác các file liên quan trên toàn stack (Database $\rightarrow$ Backend Service/Agent $\rightarrow$ FastAPI Router $\rightarrow$ React Frontend) bằng công cụ tìm kiếm hoặc ủy quyền cho Sub-agent `codebase-explorer`.
  - Trình bày bản kế hoạch ngắn gọn (5–10 dòng):
    - Các file và hàm sẽ can thiệp.
    - Logic thay đổi phẫu thuật (Minimal Diff) và ảnh hưởng đến API Contract (nếu có).
    - Các trường hợp biên trong môi trường thực tế (network timeout, dữ liệu rỗng, mất kết nối LLM, concurrency) và cách xử lý.
  - **CHƯA ĐƯỢC CHỈNH SỬA CODE** ở bước này khi kế hoạch chưa rõ ràng hoặc người dùng yêu cầu xem trước.
- **Bước 2: Mở Khóa & Thực Thi (Unlock & Execute):**
  - Chỉ can thiệp mã nguồn khi kế hoạch đã được chốt.
  - Thực hiện đúng theo phạm vi đã vạch ra, không tự ý mở rộng phạm vi (Scope Creep).

---

## 3. Vệ Sinh Ngữ Cảnh (Context Hygiene & Call Graph Navigation)

- **Tránh ngộ độc ngữ cảnh:** Không nạp tràn lan hàng chục file mã nguồn vào cùng một phiên làm việc để giữ độ chính xác cao nhất choMain Agent.
- **Nguyên tắc đọc file:**
  - Định vị dòng trước bằng `run_command` (`Select-String` / `grep`) hoặc phân tích sơ đồ gọi hàm (Call Graph).
  - Luôn sử dụng `StartLine` và `EndLine` khi đọc các file lớn để chỉ nạp đúng phân đoạn cần xử lý.
- **Ủy quyền cho Sub-agent:**
  - Khi cần khảo sát kiến trúc hoặc truy vết luồng dữ liệu diện rộng (> 3 file), triệu hồi Sub-agent `codebase-explorer`. Sub-agent sẽ khảo sát trong không gian cô lập và chỉ trả về bản tóm tắt điểm chạm cho Main Agent.

---

## 4. Cơ Chế Phản Biện Chéo Độc Lập (Adversarial Critic Gate)

- **Chống thiên kiến tự xác nhận:** Main Agent không tự đánh giá code mình vừa viết là đã hoàn hảo.
- **Nghiệm thu qua `critic-reviewer`:**
  - Trước khi commit hoặc bàn giao một cụm tính năng sản phẩm quan trọng, triệu hồi Sub-agent `critic-reviewer` để soi chiếu độc lập toàn bộ `git diff`:
    - Rủi ro `Null Reference`, lỗi chia cho 0 (`ZeroDivisionError`), hoặc ngoại lệ chưa được bắt khi gọi API ngoài.
    - Truy vấn SQL N+1, rò rỉ kết nối DB hoặc vi phạm nguyên tắc `read_only=True` của Agent.
    - Sai lệch hợp đồng dữ liệu giữa Pydantic schemas (`src/ecomreview/schemas.py`) và React Frontend (`frontend/src/`).
    - Vi phạm 7 luật kiểm duyệt kế hoạch (`R1–R7`) hoặc 6 luật an toàn CSKH (`G1–G6`).

---

## 5. Kiểm Chứng Thực Nghiệm Bắt Buộc (Verification-Driven Development - VDD)

- Tuyệt đối không dừng lại ở mức "nhìn code trông có vẻ đúng".
- Mọi thay đổi mã nguồn phải được chứng minh bằng lệnh kiểm chứng thực tế trên Terminal trước khi báo cáo hoàn tất:
  ```powershell
  # 1. Kiểm tra toàn bộ unit, API, security & regression tests
  .venv\Scripts\pytest -v

  # 2. Kiểm tra chất lượng và định dạng mã nguồn PEP 8
  .venv\Scripts\python -m ruff check .
  .venv\Scripts\python -m ruff format . --check
  ```
- Khi thay đổi liên quan đến giao diện React (`frontend/`), kiểm tra thêm lệnh build (`npm run build`) để đảm bảo không có lỗi cú pháp JSX/Vite.

---

## 6. Tuân Thủ Bản Quyền Dự Án (Credit Note)

- Mọi file mới hoặc sửa đổi có ý nghĩa phải có chữ ký tác quyền ở dòng cuối cùng:
  - File Python, Shell, YAML: `# CreBy: MenBoyBMN`
  - File Markdown, HTML: `<!-- CreBy: MenBoyBMN -->`

---

## 7. Quy Tắc Đặt Tên Commit Git Khi Push GitHub

- **Khi người dùng yêu cầu Agent tự tạo tên commit:**
  - Bắt buộc viết bằng **tiếng Việt**.
  - Tuyệt đối **không** sử dụng định dạng tiền tố `abc: xyz` (ví dụ: không dùng `feat: ...`, `fix: ...`, `chore: ...`, v.v.).
  - Phải đi thẳng vào nội dung `xyz` (Ví dụ: `hoàn thiện tính năng xuất báo cáo điều hành Excel và tối ưu bộ lọc CSKH`).
- **Khi người dùng tự đặt tên commit:**
  - Lấy chính xác 100% nguyên văn tên do người dùng đặt (không tự ý thêm tiền tố, dịch hoặc sửa đổi).

<!-- CreBy: MenBoyBMN -->
