# Bộ Nhớ Ngữ Cảnh Hệ Thống & Lộ Trình Sản Phẩm Production (Project Memory Context)

Tài liệu này lưu trữ kiến trúc tổng thể đang vận hành, trạng thái các phân hệ chức năng, cấu hình môi trường Production và định hướng phát triển của sản phẩm **EcomReview AI**.

---

## 1. Định Danh Sản Phẩm (Product Identity)
- **Tên Sản Phẩm:** EcomReview AI
- **Loại Hình Hệ Thống:** Nền tảng SaaS & AI Engine phân tích đánh giá khách hàng đa khía cạnh (ABSA), cảnh báo rủi ro chất lượng, tự động hóa lập kế hoạch Marketing/Vận hành và trợ lý CSKH thông minh cho thương mại điện tử.
- **Kiến Trúc Triển Khai:** Fullstack Production System (FastAPI Backend 15 RESTful Endpoints + React 18/Vite 6 Dashboard + Dual-DB PostgreSQL 16 / SQLite + Multi-Engine AI Layer).
- **Kho Lưu Trữ Tài Liệu Nền Tảng:** Các tài liệu nghiên cứu ban đầu, mô hình thử nghiệm (B2, B3, P0) và báo cáo học thuật đã được đóng gói lưu trữ tách biệt tại thư mục `Abount_System/` để giữ cho codebase chính thuần khiết chuẩn Production.

---

## 2. Trạng Thái Các Phân Hệ Sản Phẩm Cốt Lõi (Production Modules Status)

| Phân Hệ | Thành Phần Kỹ Thuật Chính | Trạng Thái | Năng Lực Vận Hành Thực Tế |
| :--- | :--- | :---: | :--- |
| **1. Tiếp Nhận & Bảo Mật Dữ Liệu** | `security.py`, `normalize.py`, `ingest_service.py` | ✅ Sẵn sàng | Tự động ẩn danh PII (SĐT/Email), lọc Prompt Injection, chuẩn hóa Teencode tiếng Việt, nạp lô dữ liệu lớn không trùng lặp (`upsert`). |
| **2. Động Cơ AI Đa Chế Độ** | `llm_provider.py`, `a1_gemini.py`, `b1_rule.py`, `factory.py` | ✅ Sẵn sàng | Chuyển đổi linh hoạt giữa Cloud Gemini Flash, Local Ollama (`qwen2.5:7b` kèm Self-Healing JSON Retry) và Rule-based Fallback (`B1`), tích hợp SHA-256 Cache. |
| **3. Thống Kê Xác Thực & Cảnh Báo** | `tools_aggregator.py`, `insight_engine.py` | ✅ Sẵn sàng | Tính toán KPI không ảo giác số, khoảng tin cậy bất đối xứng **Wilson 95% CI**, phân tích xu hướng tuần/tháng, cảnh báo đột biến bằng kiểm định **Z-test**. |
| **4. Tác Tử Lập Kế Hoạch & Kiểm Duyệt** | `planner.py`, `critic.py`, `evidence_selector.py`, `graph_runner.py` | ✅ Sẵn sàng | State-Graph tự trị: Tuyển chọn bằng chứng thực tế, sinh kế hoạch theo Playbook, kiểm duyệt nghiêm ngặt qua 7 luật `R1–R7` kèm cơ chế tự sửa lỗi (`Auto-Repair`). |
| **5. Trợ Lý CSKH & Đo Lường Tác Động** | `reply_assistant.py`, `reporting.py` | ✅ Sẵn sàng | Soạn câu trả lời khách hàng tuân thủ 6 rào chắn `G1–G6`; đo lường hiệu quả trước/sau khi duyệt kế hoạch (`Impact Tracking`); xuất báo cáo Excel 6-sheet & HTML/PDF. |
| **6. Backend API & Giao Diện Điều Hành** | `api/main.py` (15 Endpoints), `frontend/` (React + Vite + Tailwind) | ✅ Sẵn sàng | Hệ thống REST API bảo mật bằng `X-API-Key`, lưu vết kiểm toán `X-Reviewer`, xử lý tác vụ bất đồng bộ (`Background Jobs`), giao diện React trực quan 4 phân khu. |

---

## 3. Bản Đồ 15 RESTful API Endpoints Đang Vận Hành

1. `GET /api/v1/health`: Kiểm tra trạng thái sống của dịch vụ, kết nối DB, chế độ AI Engine và tổng số đánh giá.
2. `POST /api/v1/reviews/upload`: Tiếp nhận lô đánh giá mới, khử khuẩn PII, phân tích ABSA và lưu trữ an toàn.
3. `POST /api/v1/analyze/run`: Kích hoạt tiến trình phân tích ABSA và tổng hợp Insight (hỗ trợ chạy đồng bộ hoặc chạy ngầm `async_mode`).
4. `GET /api/v1/jobs/{job_id}`: Theo dõi tiến độ thực thi của các tác vụ chạy ngầm.
5. `GET /api/v1/stats/overview`: Truy xuất bảng chỉ số KPI tổng quan và tỷ lệ 8 khía cạnh kèm khoảng tin cậy Wilson 95% CI.
6. `GET /api/v1/insights`: Truy xuất danh sách 5 nhóm Insight đã qua kiểm thực số học `verify_numbers_in_statement()`.
7. `POST /api/v1/actions/generate`: Kích hoạt chu trình `Planner <-> HybridCritic (R1–R7)` để sinh kế hoạch hành động mới.
8. `GET /api/v1/actions`: Lấy danh sách đề xuất Marketing & Vận hành được sắp xếp theo điểm ưu tiên `priority_score`.
9. `POST /api/v1/actions/{id}/decision`: Phê duyệt, chỉnh sửa hoặc từ chối đề xuất (`APPROVED`, `EDITED`, `REJECTED`) kèm lưu vết người duyệt.
10. `GET /api/v1/reviews`: Tìm kiếm, lọc và phân trang danh sách đánh giá theo khía cạnh, cảm xúc, sàn TMĐT và số sao.
11. `GET /api/v1/trends`: Truy xuất chuỗi thời gian (theo tuần/tháng) phục vụ biểu đồ theo dõi sức khỏe sản phẩm.
12. `GET /api/v1/alerts`: Lấy danh sách cảnh báo nóng khi tỷ lệ phàn nàn ở một khía cạnh tăng đột biến có ý nghĩa thống kê.
13. `POST /api/v1/reviews/{id}/reply-draft`: Tự động soạn thảo phản hồi CSKH an toàn (đã kiểm định qua 6 luật `G1–G6`).
14. `GET /api/v1/actions/{id}/impact`: Đánh giá hiệu quả thực tế trước và sau khi triển khai hành động đã phê duyệt.
15. `GET /api/v1/reports/export`: Xuất báo cáo điều hành định dạng Excel 6-sheet (`.xlsx`) hoặc bản in HTML/PDF.

---

## 4. Các Tham Số Cấu Hình Vận Hành (Production Configuration Parameters)

### 4.1. Biến Môi Trường & Động Cơ Hệ Thống (`.env`)
- `ECOMREVIEW_DB_BACKEND`: `"postgres"` (Production/Docker) hoặc `"sqlite"` (Local/Standalone).
- `DATABASE_URL` & `DATABASE_URL_RO`: Chuỗi kết nối đọc-ghi cho Backend và chuỗi kết nối chỉ đọc (`READ-ONLY`) dành riêng cho các truy vấn của Agent.
- `ECOMREVIEW_API_KEY`: Khóa bảo mật xác thực qua header `X-API-Key` cho các endpoint thay đổi dữ liệu.
- `ECOMREVIEW_CORS_ORIGINS`: Danh sách các domain Frontend được phép gọi API.
- `DEMO_CACHE_MODE`: `"true"` hoặc `"false"` (ưu tiên tra cứu cache SHA-256 trước khi gọi LLM để tiết kiệm chi phí và tăng tốc độ phản hồi).
- `GEMINI_API_KEY` & `OLLAMA_BASE_URL`: Cấu hình kết nối cho `UnifiedLLMClient` (hỗ trợ cả Cloud Gemini Flash và Local Ollama `qwen2.5:7b`).

### 4.2. Tham Số Điều Phối & Kỷ Cương Kỹ Thuật Antigravity (AGY Tuning)
- `AGENT_OPERATING_MODE = "CONSERVATIVE_SURGICAL_PRODUCTION"`: Chế độ phẫu thuật tối thiểu, ưu tiên tính ổn định, bảo mật và hiệu năng vận hành thực tế.
- `MINIMAL_DIFF_STRICT = True`: Nghiêm cấm tự ý format cả file, đổi tên biến hoặc phá vỡ API contract.
- `PLAN_GATE_REQUIRED = True`: Bắt buộc lập kế hoạch ngắn gọn (Bước 1: Khóa tay) trước khi can thiệp code đa file hoặc xử lý bug khó (Bước 2: Mở khóa).
- `CONTEXT_POLLUTION_GUARD_THRESHOLD = 3`: Khi cần khảo sát > 3 file lớn hoặc truy vết luồng dữ liệu E2E, bắt buộc triệu hồi Subagent `codebase-explorer`.
- `ADVERSARIAL_CRITIC_GATE = True`: Triệu hồi Subagent `critic-reviewer` soi chiếu `git diff` độc lập trước khi hoàn tất tính năng.
- `VDD_VERIFICATION_REQUIRED = True`: Bắt buộc chạy kiểm thử thực tế trên Terminal trước khi báo cáo hoàn thành:
  - `.venv\Scripts\pytest -v` (100% Passed)
  - `.venv\Scripts\python -m ruff check .` (0 lỗi lint)
  - `.venv\Scripts\python -m ruff format . --check` (100% chuẩn format PEP 8)
- `CREDIT_SIGNATURE = "# CreBy: MenBoyBMN" | "<!-- CreBy: MenBoyBMN -->"`

---

## 5. Mẫu Câu Lệnh Điều Phối Nhanh Cho Kỹ Sư Sản Phẩm

1. **Khi phát triển tính năng sản phẩm mới (Fullstack/Backend/Frontend):**
   > *"Tôi cần bổ sung tính năng [Tên tính năng] cho sản phẩm. Bước 1: Hãy gọi Sub-agent `codebase-explorer` để khảo sát điểm chạm từ Database -> FastAPI -> React UI. Bước 2: Trình bày kế hoạch Minimal Diff và các edge cases thực tế. CHƯA ĐƯỢC SỬA FILE cho đến khi kế hoạch được chốt."*
2. **Khi xử lý sự cố vận hành hoặc tối ưu hiệu năng (Bug Fix / Optimization):**
   > *"Hệ thống đang gặp vấn đề [Mô tả lỗi / Log]. Hãy truy vết nguyên nhân gốc rễ, sửa đúng điểm lỗi (Minimal Diff), viết bổ sung test case chống tái phát, chạy `.venv\Scripts\pytest -v` và gọi `critic-reviewer` kiểm định `git diff`."*
3. **Khi nghiệm thu trước khi phát hành / commit:**
   > *"Hãy gọi Sub-agent `critic-reviewer` rà soát toàn bộ `git diff` hiện tại theo tiêu chuẩn Production: an toàn API, hiệu năng DB, tính toàn vẹn Pydantic schema, 7 luật R1–R7 và 6 luật G1–G6. Sau đó chạy bộ kiểm chứng VDD."*

<!-- CreBy: MenBoyBMN -->
