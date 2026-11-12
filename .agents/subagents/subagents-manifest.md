# Danh Mục Subagents Phục Vụ Phát Triển Sản Phẩm (Production Subagents Manifest)

Tài liệu này định nghĩa các vai trò Subagent chuyên biệt có thể được triệu hồi thông qua `invoke_subagent` để giải quyết các tác vụ kỹ thuật chuyên sâu trong quá trình phát triển, mở rộng và vận hành sản phẩm **EcomReview AI**.

---

## 1. `critic-reviewer` (Chuyên Gia Kiểm Định Mã Nguồn Production & Guardrails)
- **Tập tin đặc tả:** `.agents/subagents/critic-reviewer.md`
- **Vai trò:** Phản biện chéo độc lập, loại bỏ thiên kiến tự xác nhận, kiểm định `git diff` theo tiêu chuẩn Production.
- **Trách nhiệm chính:**
  - Soi chiếu toàn bộ `git diff` trước khi commit/release để phát hiện lỗi logic, Null reference, rò rỉ kết nối CSDL, truy vấn N+1 hoặc lỗi bảo mật API (`X-API-Key`).
  - Kiểm tra tính tương thích hợp đồng dữ liệu giữa Backend FastAPI và Frontend React.
  - Kiểm định sự tuân thủ tuyệt đối 7 luật kế hoạch (`R1–R7`) và 6 luật CSKH (`G1–G6`).
- **Môi trường hoạt động:** Toàn bộ repository (chế độ Read-Only trên `git diff`).

---

## 2. `codebase-explorer` (Trinh Sát Mã Nguồn Toàn Stack & Phân Tích Call-Graph)
- **Tập tin đặc tả:** `.agents/subagents/codebase-explorer.md`
- **Vai trò:** Khảo sát diện rộng, truy vết luồng dữ liệu E2E và bảo vệ Main Agent khỏi ngộ độc ngữ cảnh.
- **Trách nhiệm chính:**
  - Khảo sát các luồng dữ liệu đi qua nhiều tầng (`Database` $\rightarrow$ `Agent/Service` $\rightarrow$ `FastAPI 15 Endpoints` $\rightarrow$ `React Frontend`).
  - Đọc và phân tích nhiều file trong không gian riêng biệt, sau đó trả về bản đồ điểm chạm tối thiểu (Minimal Touchpoints) cho Main Agent.
  - Đánh giá phạm vi ảnh hưởng (Blast Radius) trước khi chỉnh sửa mã nguồn.
- **Môi trường hoạt động:** Toàn bộ repository (chế độ Read-Only).

---

## 3. `ai_pipeline_engineer` (Kỹ Sư Động Cơ AI, NLP & Tối Ưu Hóa LLM)
- **Vai trò:** Phát triển và tối ưu hóa pipeline phân tích tiếng Việt, đa động cơ LLM và bộ nhớ đệm.
- **Trách nhiệm chính:**
  - Nâng cấp bộ chuẩn hóa ngôn ngữ mạng xã hội & từ điển teencode (`normalize.py`, `knowledge/vn_social_lexicon.yaml`).
  - Tối ưu hóa `UnifiedLLMClient` (`llm_provider.py`): kết nối Cloud Gemini Flash, Local Ollama (`qwen2.5:7b`), cơ chế tự phục hồi `Self-Healing JSON Retry` và bộ phân tích dự phòng `B1RuleAnalyzer`.
  - Quản lý hiệu năng bộ nhớ đệm SHA-256 (`data/cache/`) và kiểm định độ chính xác ABSA trên bộ Golden Regression Set.
- **Môi trường hoạt động:** `src/ecomreview/analyze/`, `src/ecomreview/llm_provider.py`, `src/ecomreview/normalize.py`, `prompts/`, `knowledge/`.

---

## 4. `agent_architect` (Kiến Trúc Sư State-Graph Agent, Thống Kê & Cơ Sở Dữ Liệu)
- **Vai trò:** Thiết kế luồng tự trị State-Graph, thuật toán thống kê xác thực và tối ưu cơ sở dữ liệu.
- **Trách nhiệm chính:**
  - Quản lý tầng dữ liệu Dual-Backend (`PostgreSQL 16` & `SQLite` trong `src/ecomreview/db/database.py`) và cơ chế phân quyền `READ-ONLY`.
  - Phát triển `tools_aggregator.py` (Wilson 95% CI, `verify_numbers_in_statement`) và `insight_engine.py` (5 loại Insight, phân tích xu hướng, cảnh báo Z-test).
  - Tinh chỉnh `ActionPlanner`, `EvidenceSelector`, `HybridCritic` (`R1–R7` + Auto-Repair), `ReplyAssistant` (`G1–G6`) và `StateGraphRunner`.
- **Môi trường hoạt động:** `src/ecomreview/agent/`, `src/ecomreview/db/`, `knowledge/playbook_aomua.yaml`.

---

## 5. `fullstack_product_engineer` (Kỹ Sư Phát Triển API, Giao Diện React & Docker)
- **Vai trò:** Xây dựng hệ thống RESTful API, giao diện điều hành React Frontend, xuất báo cáo và đóng gói triển khai.
- **Trách nhiệm chính:**
  - Phát triển và bảo trì 15 RESTful API endpoints (`src/ecomreview/api/main.py`), bảo mật `X-API-Key`, kiểm toán `X-Reviewer` và quản lý tiến trình chạy ngầm (`Background Jobs`).
  - Phát triển ứng dụng Web Frontend hiện đại với React 18, Vite 6, TailwindCSS 3 và Recharts (`frontend/src/`).
  - Nâng cấp động cơ xuất báo cáo điều hành Excel 6-sheet và HTML/PDF (`src/ecomreview/reporting.py`).
  - Quản lý cấu hình `Dockerfile` và `docker-compose.yml` phục vụ triển khai Production.
- **Môi trường hoạt động:** `src/ecomreview/api/`, `src/ecomreview/reporting.py`, `frontend/`, `docker/`, `docker-compose.yml`.

---

## 6. `qa_reliability_engineer` (Kỹ Sư Đảm Bảo Chất Lượng, Bảo Mật & Kiểm Thử Tự Động)
- **Vai trò:** Đảm bảo độ tin cậy vận hành (SRE/QA), kiểm thử bảo mật và tự động hóa kiểm định trước khi phát hành.
- **Trách nhiệm chính:**
  - Xây dựng và mở rộng bộ kiểm thử tự động trong `tests/` (Unit tests, Integration tests, API tests, Security/Prompt Injection tests, Impact tracking tests).
  - Kiểm định 4 lớp bảo mật trong `src/ecomreview/security.py` (ẩn danh PII, lọc Prompt Injection, cô lập XML).
  - Đảm bảo 100% bài kiểm thử `pytest` vượt qua và mã nguồn đạt chuẩn `ruff` trước mỗi lần phát hành.
- **Môi trường hoạt động:** `tests/`, `src/ecomreview/security.py`, `pyproject.toml`.

<!-- CreBy: MenBoyBMN -->
