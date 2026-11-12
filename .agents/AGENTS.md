# EcomReview AI - Sổ Tay Kỹ Thuật & Hướng Dẫn Phát Triển Sản Phẩm Production

Chào mừng bạn đến với không gian làm việc của **EcomReview AI**. Tài liệu này thiết lập các tiêu chuẩn kỹ thuật, nguyên tắc kiến trúc bất biến, quy chuẩn vận hành cấp độ sản phẩm thực tế (Production-Ready) và quy tắc hành vi bắt buộc dành cho mọi AI Agent và kỹ sư phần mềm trong dự án.

---

## 1. Tầm Nhìn Sản Phẩm & Triết Lý Cốt Lõi (Production-First Philosophy)

**EcomReview AI** là nền tảng SaaS / AI Engine thực chiến chuyên phân tích phản hồi khách hàng tiếng Việt theo khía cạnh (**Aspect-Based Sentiment Analysis — ABSA**), phát hiện sớm rủi ro chất lượng hàng hóa, tự động lập kế hoạch hành động Marketing / Vận hành khả thi và hỗ trợ chăm sóc khách hàng (CSKH) tự động cho các gian hàng thương mại điện tử (**Shopee**, **TikTok Shop**).

- **Định hướng cốt lõi (Production-First):** Xây dựng một sản phẩm phần mềm hoàn chỉnh, ổn định, bảo mật, có khả năng chịu lỗi cao (fault-tolerant), sẵn sàng vận hành thực tế hàng ngày tại các doanh nghiệp vừa và nhỏ (SMEs) thay vì chỉ dừng ở mô hình thử nghiệm học thuật.
- **Chu trình khép kín (Closed-Loop Operations):**
  `Thu thập & Khử khuẩn PII` $\rightarrow$ `Phân tích ABSA đa tầng` $\rightarrow$ `Thống kê xác thực & Cảnh báo sớm (Z-test)` $\rightarrow$ `Lập kế hoạch & Kiểm duyệt R1–R7` $\rightarrow$ `Phê duyệt thực thi & Soạn phản hồi CSKH G1–G6` $\rightarrow$ `Đo lường hiệu quả sau can thiệp (Impact Tracking) & Xuất báo cáo điều hành`.
- **Ngành hàng triển khai trọng tâm:** Ngành hàng Áo mưa thời trang & tiện lợi (và dễ dàng mở rộng sang các ngành hàng tiêu dùng nhanh/thời trang khác thông qua cấu hình Playbook YAML).

---

## 2. Năm Nguyên Tắc Kiến Trúc Bất Biến (Production Architectural Invariants)

Mọi thay đổi mã nguồn, bổ sung tính năng hoặc tối ưu hóa hệ thống bắt buộc phải tuân thủ nghiêm ngặt 5 nguyên tắc bất biến sau:

1. **Số Liệu Xác Thực Tuyệt Đối (Zero Numeric Hallucination):**
   - Tuyệt đối **không** để LLM tự tính toán, cộng trừ hoặc suy đoán số liệu thống kê từ văn bản thô.
   - 100% các chỉ số KPI (tổng đánh giá, tỷ lệ phàn nàn, khoảng tin cậy bất đối xứng **Wilson 95% CI**, biến động theo tuần/tháng, kiểm định **Z-test** cảnh báo đột biến) phải được tính toán xác định qua SQL/Python (`tools_aggregator.py`) và kiểm thực chéo bằng `verify_numbers_in_statement()` trước khi xuất ra API hoặc giao diện.

2. **Tính Căn Cứ, Khả Thi & Đo Lường Được (Grounded, Actionable & Measurable Proposals):**
   - Mọi đề xuất hành động (`ActionProposal`) bắt buộc gắn kèm `insight_ids` hợp lệ và tối thiểu **2 mã đánh giá thực tế (`evidence_review_ids`)** từ CSDL làm bằng chứng.
   - Phân tách rõ ràng giữa:
     - **Hành động Marketing (`is_marketing = True`):** `LISTING_UPDATE`, `CONTENT`, `REVIEW_REPLY`, `PROMOTION`, `CUSTOMER_CARE`.
     - **Hành động Vận hành / Sản phẩm (`is_marketing = False`):** `PRODUCT_FIX`, `OPS`.
   - Hỗ trợ luồng phê duyệt có lưu vết kiểm toán (`APPROVED`, `EDITED`, `REJECTED` kèm `X-Reviewer`) và đo lường tác động thực tế trước/sau can thiệp (`Impact Tracking`).

3. **Bảo Mật Đa Tầng & An Toàn Dữ Liệu Khách Hàng (4-Layer Defense-in-Depth & API Security):**
   - Đánh giá từ sàn TMĐT là dữ liệu ngoại vi không đáng tin cậy. Bắt buộc bảo vệ qua 4 lớp:
     1. Tự động ẩn danh thông tin cá nhân (`scrub_pii`: SĐT, Email, đường dẫn lạ) và khử khuẩn chuỗi đầu vào (loại bỏ ký tự điều khiển, giới hạn độ dài, phát hiện mẫu Prompt Injection).
     2. Cô lập dữ liệu khách hàng trong thẻ XML `<customer_review>...</customer_review>`.
     3. Ép kiểu đầu ra nghiêm ngặt qua Pydantic v2 (`Structured Output`) kèm cơ chế tự phục hồi (`Self-Healing JSON Retry`).
     4. Kết nối CSDL ở chế độ chỉ đọc (`read_only=True`) cho toàn bộ tiến trình suy luận của Agent; bảo vệ REST API bằng `X-API-Key` và cấu hình CORS chặt chẽ.

4. **Kiến Trúc State-Graph Thuần & Kiểm Duyệt Tự Động Kép (Pure Python State-Graph & Dual Guardrails):**
   - Sử dụng Python State-Graph thuần (`graph_runner.py`), không phụ thuộc vào các framework cồng kềnh dễ gãy khi nâng cấp phiên bản.
   - **Kiểm duyệt Kế hoạch (`HybridCritic` R1–R7 + Auto-Repair):** Mọi kế hoạch phải vượt qua 7 luật xác định (R1–R7) trước khi đến tay người vận hành.
   - **Kiểm duyệt Phản hồi CSKH (`ReplyAssistant` G1–G6):** Mọi bản nháp trả lời khách hàng phải tuân thủ 6 rào chắn an toàn (không cam kết quá đà, không gạ sửa sao, không điều hướng giao dịch ngoài sàn, không lộ PII, đúng độ dài và giải quyết đúng khía cạnh bị phàn nàn).

5. **Khả Năng Chịu Lỗi Cao & Tối Ưu Chi Phí Vận Hành (High Availability & Cost Resilience):**
   - **Đa động cơ AI (`UnifiedLLMClient`):** Hỗ trợ chuyển đổi mượt mà giữa Cloud AI (`Gemini Flash`) và Local AI (`Ollama qwen2.5:7b`), tự động sửa lỗi JSON lệch chuẩn và tự động chuyển về bộ phân tích quy tắc xác định (`B1RuleAnalyzer`) khi mất kết nối mạng hoặc hết hạn mức API.
   - **Cơ sở dữ liệu linh hoạt & Cache thông minh:** Hỗ trợ song song **PostgreSQL 16** (môi trường Production/Docker) và **SQLite** (triển khai cục bộ gọn nhẹ), kết hợp bộ nhớ đệm SHA-256 (`DEMO_CACHE_MODE`) giúp giảm thiểu chi phí gọi LLM cho các đánh giá trùng lặp.

---

## 3. Khung Vận Hành Tối Ưu Hóa Năng Lực Antigravity (AGY Optimization Framework)

Để đảm bảo chất lượng mã nguồn cấp độ Production, Antigravity Agent bắt buộc vận hành theo **5 Kỷ Cương Tác Chiến Phẫu Thuật**:

1. **Kỷ Cương Phẫu Thuật Tối Thiểu (Minimal Diff & Anti-Over-Engineering):**
   - Phong cách lập trình: **Bảo thủ & Phẫu thuật (Conservative & Surgical)**.
   - Chỉ sửa đổi chính xác số dòng code, hàm số hoặc file liên quan trực tiếp đến mục tiêu công việc.
   - Tuyệt đối **không** tự ý refactor các module xung quanh, không đổi tên biến/hàm/endpoint đang hoạt động ổn định, không thêm các lớp trừu tượng thừa thãi.
   - Ưu tiên công cụ `edit_file` với đoạn `Target` chuẩn xác từng ký tự; tránh ghi đè toàn bộ file mã nguồn lớn khi chỉ sửa một phần nhỏ.

2. **Chiến Thuật Plan Gate 2 Bước (Chống Premature Coding):**
   - **Bước 1 (Lock):** Khi nhận yêu cầu tính năng mới hoặc xử lý lỗi phức tạp, trước tiên phải phân tích luồng dữ liệu, xác định các file bị ảnh hưởng (Backend/Frontend/DB), liệt kê edge cases và phác thảo giải pháp Minimal Diff. **CHƯA ĐƯỢC CHỈNH SỬA MÃ NGUỒN** khi kế hoạch chưa rõ ràng.
   - **Bước 2 (Unlock & Execute):** Sau khi kế hoạch đã được xác định rõ, tiến hành thực thi chuẩn xác theo đúng phạm vi, đảm bảo không phá vỡ hợp đồng dữ liệu (API Contract) giữa Backend và Frontend.

3. **Vệ Sinh Ngữ Cảnh & Điều Phối Sub-Agent (Context Hygiene & Subagent Delegation):**
   - Giữ ngữ cảnh của Main Agent luôn tinh gọn để tối ưu độ chính xác suy luận.
   - Khi cần khảo sát diện rộng (đọc > 3 file lớn hoặc truy vết luồng dữ liệu E2E từ Database $\rightarrow$ FastAPI $\rightarrow$ React UI), **bắt buộc ủy quyền cho Sub-agent `codebase-explorer`**.
   - Khi đọc file trực tiếp, luôn sử dụng `StartLine` và `EndLine` để chỉ nạp đúng phân đoạn mã nguồn cần thiết.

4. **Cơ Chế Phản Biện Chéo Độc Lập (Adversarial Critic Gate):**
   - Sau khi hoàn thành một cụm chức năng hoặc trước khi commit mã nguồn, triệu hồi Sub-agent `critic-reviewer` với tâm thế phản biện khắt khe độc lập:
     - Soi chiếu toàn bộ `git diff` để bắt lỗi: Null reference, rò rỉ tài nguyên DB connection, truy vấn N+1, sai lệch Pydantic schema hoặc hỏng giao tiếp API với React Frontend.
     - Kiểm định sự tuân thủ 7 luật `R1–R7` và 6 luật `G1–G6`.

5. **Quy Trình Kiểm Chứng Bắt Buộc (Verification-Driven Development - VDD):**
   - Không bao giờ giả định code đã chạy đúng nếu chưa thực thi kiểm thử.
   - Sau mỗi lần can thiệp mã nguồn, bắt buộc chạy lệnh kiểm chứng thực tế trên Terminal (`pytest -v`, `ruff check .`, `ruff format . --check`) và kiểm tra build/healthcheck của hệ thống.

---

## 4. Ngăn Xếp Công Nghệ Sản Phẩm (Production Technical Stack)

| Hạng Mục | Công Nghệ | Chi Tiết Kỹ Thuật Trong Production |
| :--- | :--- | :--- |
| **Ngôn Ngữ & Runtime** | Python 3.11+ & Node.js | Môi trường ảo `.venv` cho Backend, Vite/Node cho Frontend |
| **AI / LLM Layer** | UnifiedLLMClient | Cloud `Gemini Flash` (`google-genai`), Local `Ollama (qwen2.5:7b)`, Self-Healing JSON Retry, `B1RuleAnalyzer` Fallback |
| **Cơ Sở Dữ Liệu** | PostgreSQL 16 & SQLite | Hỗ trợ Dual-Backend (`database.py`), tách biệt kết nối Read-Write và Read-Only (`DATABASE_URL_RO`) |
| **Backend REST API** | FastAPI + Uvicorn | 15 RESTful API Endpoints, OpenAPI 3.1 / Swagger UI, xác thực `X-API-Key`, kiểm toán `X-Reviewer`, Background Jobs |
| **Frontend Web App** | React 18 + Vite 6 | TailwindCSS 3, Recharts trực quan hóa dữ liệu, Lucide Icons, giao diện điều hành hiện đại (`frontend/`) |
| **Báo Cáo Điều Hành** | OpenPyXL + HTML/PDF | Xuất báo cáo quản trị Excel 6-sheet chuyên sâu (`.xlsx`) và báo cáo HTML chuẩn in ấn PDF (`reporting.py`) |
| **Đóng Gói & Kiểm Thử** | Docker Compose & Pytest | Điều phối container (`db`, `api`), bộ kiểm thử tự động `pytest`, kiểm tra chất lượng mã nguồn với `ruff` |

---

## 5. Cấu Trúc Thư Mục Chuẩn Của Hệ Thống

```text
ecomreview/
├── data/
│   ├── cache/                # Bộ nhớ đệm phản hồi AI theo SHA-256 (tiết kiệm token)
│   └── ecomreview.db         # Cơ sở dữ liệu SQLite cục bộ (khi chạy chế độ local)
├── docker/
│   ├── api/Dockerfile        # Dockerfile đóng gói dịch vụ FastAPI Backend
│   └── db/init.sql           # Script khởi tạo schema và quyền READ-ONLY trên PostgreSQL 16
├── frontend/                 # Ứng dụng Web Frontend (React 18 + Vite 6 + TailwindCSS + Recharts)
│   ├── src/
│   │   ├── api/client.js     # HTTP Client kết nối 15 endpoints của FastAPI Backend
│   │   ├── components/       # OverviewTab, InsightsAlertsTab, ActionsTab, ReviewsCskhTab, Modals
│   │   └── constants/        # Định nghĩa nhãn hiển thị 8 khía cạnh ABSA
│   └── package.json
├── knowledge/
│   ├── playbook_aomua.yaml   # Tri thức miền vận hành (12 mẫu hành động chuẩn & ngưỡng kích hoạt)
│   └── vn_social_lexicon.yaml # Từ điển chuẩn hóa Teencode, tiếng lóng & từ khóa cảm xúc TMĐT
├── prompts/                  # Quản lý phiên bản System Prompts (analyzer, planner, reply)
├── results/
│   └── traces/               # Lưu vết thực thi State-Graph (JSON trace logs phục vụ kiểm toán)
├── scripts/
│   ├── ingest.py             # Công cụ CLI nạp dữ liệu hàng loạt vào hệ thống
│   ├── migrate_sqlite_to_pg.py # Công cụ đồng bộ dữ liệu từ SQLite sang PostgreSQL 16
│   └── seed_demo.py          # Khởi tạo dữ liệu vận hành mẫu cho môi trường mới
├── src/ecomreview/
│   ├── schemas.py            # Hợp đồng dữ liệu Pydantic v2 toàn hệ thống
│   ├── security.py           # Khử khuẩn Prompt Injection, ẩn danh PII & cô lập thẻ XML
│   ├── normalize.py          # Chuẩn hóa văn bản tiếng Việt & giải mã Teencode
│   ├── llm_provider.py       # UnifiedLLMClient (Cloud Gemini + Local Ollama + Auto-Repair)
│   ├── ingest_service.py     # Dịch vụ tiếp nhận, làm sạch và phân tích lô đánh giá mới
│   ├── reporting.py          # Động cơ xuất báo cáo điều hành Excel 6-sheet & HTML/PDF
│   ├── db/
│   │   └── database.py       # Quản lý kết nối PostgreSQL 16 / SQLite & phân quyền Read-Only
│   ├── analyze/
│   │   ├── a1_gemini.py      # Bộ phân tích ABSA bằng LLM (Structured Output + Cache)
│   │   ├── b1_rule.py        # Bộ phân tích quy tắc tốc độ cao (Deterministic Fallback)
│   │   └── factory.py        # Factory khởi tạo bộ phân tích theo cấu hình vận hành
│   ├── agent/
│   │   ├── tools_aggregator.py # Tính toán KPI, Wilson 95% CI & kiểm thực số học
│   │   ├── insight_engine.py # Phát hiện 5 loại Insight, xu hướng thời gian & cảnh báo Z-test
│   │   ├── evidence_selector.py # Tuyển chọn đánh giá bằng chứng tiêu biểu nhất
│   │   ├── planner.py        # Lập kế hoạch hành động Marketing & Vận hành
│   │   ├── critic.py         # Kiểm duyệt tự động theo 7 luật R1–R7 & Auto-Repair
│   │   ├── graph_runner.py   # Điều phối luồng State-Graph E2E
│   │   └── reply_assistant.py # Trợ lý soạn thảo phản hồi CSKH tuân thủ 6 luật G1–G6
│   └── api/
│       ├── main.py           # 15 RESTful API Endpoints phục vụ ứng dụng Production
│       └── security_deps.py  # Middleware xác thực X-API-Key & X-Reviewer
├── tests/                    # Bộ kiểm thử tự động toàn diện (Unit, API, Security, Regression)
├── Abount_System/            # Kho lưu trữ tài liệu thiết kế gốc, lịch sử thực nghiệm & nghiên cứu
├── docker-compose.yml        # Cấu hình triển khai dịch vụ Production (PostgreSQL + FastAPI)
├── pyproject.toml            # Cấu hình gói phần mềm, Pytest và Ruff linter
└── README.md                 # Tài liệu hướng dẫn triển khai và vận hành hệ thống
```

---

## 6. Taxonomy 8 Khía Cạnh Đánh Giá Chuẩn (ABSA Taxonomy)

Hệ thống phân tích và giám sát chất lượng sản phẩm/dịch vụ theo 8 khía cạnh cốt lõi:
1. `WATERPROOF`: Khả năng chống thấm nước, độ kín đường may ép nhiệt, chống tràn nước qua nẹp/cổ áo.
2. `MATERIAL_DURABILITY`: Chất liệu vải (dù tổ ong, PVC, EVA, tráng PU), độ bền cơ học, độ bền khóa kéo/cúc bấm.
3. `FIT_SIZE`: Độ vừa vặn kích cỡ, chiều dài vạt áo, khả năng che phủ khi ngồi xe máy hoặc đeo balo.
4. `COMFORT_USABILITY`: Sự tiện lợi khi mặc/tháo/gấp gọn, độ thoáng khí, mùi nhựa, kính chắn mưa, chụp gương.
5. `PRICE_VALUE`: Mức độ tương xứng giữa giá bán và giá trị nhận được, hiệu quả các gói khuyến mãi.
6. `PACKAGING_SHIPPING`: Chất lượng túi/hộp đóng gói, tốc độ giao hàng, tình trạng hàng khi nhận.
7. `CUSTOMER_SERVICE`: Tốc độ và thái độ tư vấn của gian hàng, quy trình hỗ trợ bảo hành và đổi trả hàng lỗi.
8. `ACCESSIBILITY_DESIGN`: Màu sắc thực tế, kiểu dáng thời trang, dải phản quang an toàn, tính thẩm mỹ.

---

## 7. Tiêu Chuẩn Kiểm Định Trước Khi Bàn Giao (Release Gate)

Trước khi kết thúc bất kỳ tác vụ kỹ thuật nào, bắt buộc thực thi bộ kiểm định sau:
```powershell
# 1. Chạy toàn bộ bộ kiểm thử tự động (Unit + Integration + API + Regression)
.venv\Scripts\pytest -v

# 2. Kiểm tra chất lượng mã nguồn và định dạng PEP 8
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format . --check
```
Mọi bản cập nhật phải đạt **100% টেস্ট Passed** và **0 lỗi lint/format**.

---

## 8. Quy Tắc Hành Vi & Ghi Chú Bản Quyền (Credit Note)

- **Ngôn ngữ giao tiếp:** Tiếng Việt (rõ ràng, đi thẳng vào giải pháp kỹ thuật và giá trị vận hành thực tế).
- **Mã nguồn & Comment:** Tiếng Anh chuyên nghiệp, tuân thủ PEP 8 và Google Style Guide.
- **Quy tắc đặt tên Commit Git khi Push lên GitHub:**
  - *Nếu người dùng yêu cầu Agent tự tạo tên commit:* Bắt buộc viết bằng **tiếng Việt**, tuyệt đối **không** dùng định dạng tiền tố `abc: xyz` (không dùng `feat:`, `fix:`, `chore:`, ...), mà phải đi thẳng vào nội dung `xyz` (Ví dụ: `nâng cấp bộ lọc bảo mật API và tối ưu tốc độ xuất báo cáo Excel`).
  - *Nếu người dùng tự đặt tên commit:* Lấy chính xác 100% nguyên văn tên do người dùng đặt (không tự ý thêm tiền tố, dịch hoặc sửa đổi).
- **Credit Note bắt buộc:** Mọi file mới được tạo hoặc sửa đổi có ý nghĩa phải có chữ ký tác quyền ở dòng cuối:
  - File Python, Shell, YAML: `# CreBy: MenBoyBMN`
  - File Markdown, HTML: `<!-- CreBy: MenBoyBMN -->`

<!-- CreBy: MenBoyBMN -->
