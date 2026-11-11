# EcomReview AI - Sổ Tay Kỹ Thuật & Hướng Dẫn Dành Cho AI Agent

Chào mừng bạn đến với không gian làm việc của **EcomReview AI**. Tài liệu này thiết lập các tiêu chuẩn kỹ thuật, nguyên tắc kiến trúc bất biến, quy chuẩn nghiên cứu khoa học và quy tắc hành vi bắt buộc dành cho mọi AI Agent và lập trình viên trong dự án.

---

## 1. Tổng Quan Dự Án & Triết Lý Cốt Lõi

**EcomReview AI** là hệ thống AI Agent thông minh tự động phân tích phản hồi khách hàng tiếng Việt (Aspect-Based Sentiment Analysis - ABSA) và lập kế hoạch hành động marketing / tối ưu sản phẩm khả thi cho doanh nghiệp vừa và nhỏ (SMEs).

- **Mục tiêu kép (Dual-Objective):** Đạt chuẩn nghiên cứu khoa học học thuật (Báo cáo 30–50 trang, 15–25 trích dẫn, 3 Baselines, kiểm định thống kê Bootstrap CI 95%, phân tích lỗi Pareto) kết hợp hoàn thiện sản phẩm công nghệ thực chiến (FastAPI, PostgreSQL 16, Streamlit Dashboard 4 trang, đóng gói Docker Compose 1-click, video demo 5–10 phút).
- **Trường hợp điển hình (Case Study):** Sản phẩm Áo mưa thời trang & tiện lợi trên 2 sàn thương mại điện tử **Shopee** và **TikTok Shop**.
- **Thời lượng thực hiện:** 10 tuần / 1 kỹ sư kiêm nghiên cứu viên.

---

## 2. Các Nguyên Tắc Kiến Trúc Bất Biến (Architectural Invariants)

Mọi thay đổi mã nguồn hoặc đề xuất kỹ thuật bắt buộc phải tuân thủ nghiêm ngặt 5 nguyên tắc sau:

1. **Số Liệu Xác Thực Tuyệt Đối (Zero-Hallucination Metrics via SQL/Python Aggregator):**
   - Tuyệt đối **không** để LLM tự tính toán, cộng trừ hoặc bịa số liệu thống kê từ văn bản thô.
   - 100% các chỉ số (tổng review, tỷ lệ hài lòng, tỷ lệ tiêu cực, Wilson score confidence interval, xếp hạng vấn đề cốt lõi) phải được tính toán bằng truy vấn SQL trên PostgreSQL hoặc hàm Python thuần xác định trước khi đưa vào ngữ cảnh của Agent.

2. **Tính Căn Cứ & Khả Thi Trong Hành Động (Grounded & Actionable Proposals):**
   - Mọi đề xuất hành động marketing (`ActionProposal`) sinh ra bởi Agent bắt buộc phải gắn kèm bằng chứng: `insight_ids` hợp lệ và tối thiểu 2 `evidence_review_ids` thực tế từ tập dữ liệu.
   - Phân tách rõ ràng giữa:
     - **Hành động Marketing (`is_marketing = True`):** `LISTING_UPDATE`, `CONTENT`, `REVIEW_REPLY`, `PROMOTION`, `CUSTOMER_CARE`.
     - **Hành động Vận hành / Sản phẩm (`is_marketing = False`):** `PRODUCT_FIX`, `OPS`.

3. **Bảo Mật & Phòng Thủ Đa Tầng Trước Prompt Injection (Defense-in-Depth Security):**
   - Review từ khách hàng là dữ liệu ngoại vi không đáng tin cậy. Bắt buộc bảo vệ qua 4 lớp:
     1. Khử khuẩn chuỗi (Sanitize, loại bỏ ký tự điều khiển, giới hạn độ dài).
     2. Đóng gói trong thẻ XML cách ly `<customer_review>...</customer_review>`.
     3. Kiểm thực chặt chẽ đầu ra qua Pydantic Schemas (`Structured Output`).
     4. Kết nối Database ở quyền chỉ đọc (`READ-ONLY`) đối với các tiến trình chạy phân tích của Agent.

4. **Kiến Trúc Tinh Gọn — State-Graph Thuần (Pure Python State-Graph):**
   - Vòng lặp Agent: `Aggregator (SQL/CI)` $\rightarrow$ `Insight Engine` $\rightarrow$ `Action Planner` $\rightleftarrows$ `Hybrid Critic (7 Luật xác định R1–R7 + LLM-Judge)` $\rightarrow$ `Human Approval Gate`.
   - Sử dụng Python State-Graph tự phát triển, **không** phụ thuộc vào các framework cồng kềnh (như LangChain / CrewAI) để tránh xung đột phiên bản, khó debug và gãy pipeline trong quá trình bảo vệ đồ án.

5. **Tính Nghiêm Ngặt & Tái Lập Được (Scientific Rigor & Reproducibility):**
   - Cố định Random Seed (`seed=42`) cho mọi thí nghiệm chia tách dữ liệu và khởi tạo mô hình.
   - Đánh giá có khoảng tin cậy Bootstrap CI 95% ($B=1.000$).
   - Kiểm định độ đồng thuận gán nhãn bằng Cohen's Kappa / Fleiss' Kappa.
   - Thử nghiệm mù (Blind A/B Evaluation) khi so sánh Baseline Agent P0 và Proposed Agent P1.

---

## 3. Khung Vận Hành Tối Ưu Hóa Năng Lực Antigravity (AGY Optimization Framework)

Để khai thác tối đa sức mạnh của Gemini Flash (bộ nhớ 1M-2M tokens, tốc độ siêu nhanh, Sub-agent song song, chi phí tối ưu) và loại bỏ hoàn toàn các điểm yếu mặc định (Over-engineering, Scope Creep, ngộ độc ngữ cảnh, ảo giác xác nhận), Antigravity Agent bắt buộc vận hành theo **5 Kỷ Cương Tác Chiến Phẫu Thuật**:

1. **Kỷ Cương Phẫu Thuật Tối Thiểu (Minimal Diff & Anti-Over-Engineering):**
   - Phong cách lập trình: **Bảo thủ & Phẫu thuật (Conservative & Surgical)**.
   - Chỉ sửa đổi chính xác số dòng code, hàm số hoặc file liên quan trực tiếp đến mục tiêu của task.
   - Tuyệt đối **không** tự ý refactor các module xung quanh, không đổi tên biến/hàm không liên quan, không tự ý bổ sung các abstraction hoặc cấu trúc chưa được yêu cầu.
   - Ưu tiên công cụ `edit_file` với đoạn `Target` chuẩn xác từng ký tự và thụt lề; tuyệt đối tránh ghi đè toàn bộ file lớn khi chỉ cần sửa vài dòng.

2. **Chiến Thuật Plan Gate 2 Bước (Chống Premature Coding):**
   - **Bước 1 (Lock):** Khi nhận task mới hoặc phân tích bug khó, trước tiên phải phân tích luồng code, xác định danh sách file bị ảnh hưởng, vạch ra các edge cases và phác thảo giải pháp Minimal Diff. **CHƯA ĐƯỢC CHỈNH SỬA MÃ NGUỒN** khi kế hoạch chưa rõ ràng hoặc chưa đạt đồng thuận.
   - **Bước 2 (Unlock & Execute):** Sau khi kế hoạch được xác định, tiến hành thực thi chuẩn xác theo đúng phạm vi đã định, không đi chệch hướng.

3. **Vệ Sinh Ngữ Cảnh & Điều Phối Sub-Agent (Context Hygiene & Subagent Delegation):**
   - Main Agent luôn giữ ngữ cảnh sạch tinh để duy trì khả năng suy luận logic và kiến trúc ở mức cao nhất.
   - Khi cần khảo sát diện rộng (đọc hơn 3 file lớn hoặc trace luồng dữ liệu phức tạp E2E), **bắt buộc ủy quyền (delegate) cho Sub-agent chuyên biệt** (`codebase-explorer`). Sub-agent sẽ khảo sát 20-50 file trong bộ nhớ riêng của nó rồi chỉ trả về danh sách file/hàm cụ thể cho Main Agent.
   - Khi đọc file, luôn dùng `StartLine` và `EndLine` hoặc công cụ tìm kiếm có phạm vi, không nạp toàn bộ file hàng nghìn dòng vào context.

4. **Cơ Chế Phản Biện Chéo Độc Lập (Adversarial Critic Gate):**
   - Tránh thiên kiến tự xác nhận ("code mình viết ra luôn đúng").
   - Sau khi hoàn thành một cụm chức năng hoặc trước khi commit mã nguồn, triệu hồi Sub-agent `critic-reviewer` với tâm thế phản biện khắt khe độc lập:
     - Soi chiếu toàn bộ `git diff` tìm kiếm: Null reference, rò rỉ bộ nhớ, N+1 query trong SQL, lỗi phá vỡ contract Pydantic.
     - Kiểm định mức độ tuân thủ 7 luật xác định (R1–R7) trong tri thức miền áo mưa.

5. **Quy Trình Kiểm Chứng Bắt Buộc (Verification-Driven Development - VDD):**
   - Tuyệt đối không phán đoán hoặc giả định rằng code "chắc chắn đã chạy đúng".
   - Sau mỗi lần can thiệp mã nguồn, bắt buộc tự chạy lệnh kiểm chứng thực tế trên Terminal (`pytest -v`, `ruff check .`, `ruff format . --check`).
   - Với các thành phần Web/API/UI: Tự khởi chạy và kiểm tra phản hồi HTTP / giao diện thực tế trước khi bàn giao cho người dùng.

---

## 4. Ngăn Xếp Công Nghệ (Technical Stack)

| Hạng Mục | Công Nghệ | Phiên Bản / Chi Tiết Kỹ Thuật |
| :--- | :--- | :--- |
| **Ngôn Ngữ & Môi Trường** | Python | Python 3.11+, Quản lý môi trường ảo `venv` |
| **AI / LLM Trọng Tâm** | Gemini Flash | Google GenAI SDK (`google-genai`), Structured Output qua Pydantic v2 |
| **Mô Hình Học Máy & NLP** | ViSoBERT, Scikit-learn | `uitnlp/visobert` (fine-tuned Colab T4), TF-IDF + Logistic Regression, Rule Lexicon |
| **Cơ Sở Dữ Liệu** | PostgreSQL | PostgreSQL 16, psycopg / SQLAlchemy Core |
| **Backend API** | FastAPI | FastAPI 0.110+, Uvicorn, Pydantic v2 validation |
| **Giao Diện Người Dùng** | Streamlit + Plotly | Streamlit đa trang (4 trang), Plotly tương tác trực quan |
| **Kiểm Thử & Đóng Gói** | Pytest & Docker | `pytest`, `pytest-cov`, Docker Compose (`db`, `api`, `ui`) |
| **Chất Lượng Code** | Ruff | Linter & Formatter siêu tốc, quy chuẩn PEP 8 |

---

## 5. Cấu Trúc Thư Mục Chuẩn Của Dự Án

Toàn bộ mã nguồn và tài liệu tuân thủ cấu trúc sau:

```text
ecomreview/
├── data/
│   ├── raw/                  # Dữ liệu gốc Shopee/TikTok (KHÔNG commit lên Git)
│   ├── public/               # Benchmark công khai (UIT-ViSFD / VLSP)
│   ├── interim/              # Dữ liệu đã làm sạch & chuẩn hóa teencode
│   ├── gold/                 # Tập dev.jsonl, test_locked.jsonl (Shop Áo Mưa)
│   └── cache/                # Cache phản hồi Gemini theo SHA-256
├── docs/
│   ├── scope.md              # Phạm vi, RQ1–RQ3, giả thuyết nghiên cứu
│   ├── annotation_guideline.md # Hướng dẫn gán nhãn 8 khía cạnh
│   ├── data_stats.md         # Thống kê khám phá dữ liệu (EDA)
│   └── report/               # Bản thảo báo cáo 5 chương (30–50 trang)
├── knowledge/
│   └── playbook_aomua.yaml   # Tri thức miền Áo mưa (12 hành động chuẩn & guardrails)
├── models/                   # Checkpoints TF-IDF, ViSoBERT (gitignored)
├── prompts/                  # Quản lý phiên bản Prompt (analyzer, planner, critic)
├── results/                  # Bảng kết quả RQ1, RQ2, RQ3, trace logs JSON
├── scripts/                  # Scripts tiền xử lý, gán nhãn, xuất báo cáo
├── src/ecomreview/
│   ├── schemas.py            # Pydantic schemas xuyên suốt pipeline
│   ├── security.py           # Bộ lọc Prompt Injection & che giấu PII
│   ├── normalize.py          # Tiền xử lý tiếng Việt & từ điển Teencode
│   ├── db/                   # Kết nối & truy vấn PostgreSQL
│   ├── analyze/              # B1 (Rule), B2 (TF-IDF), B3 (ViSoBERT), A1 (Gemini)
│   ├── agent/                # Aggregator, InsightEngine, Planner, Critic, StateGraph
│   ├── api/                  # FastAPI router & services
│   ├── ui/                   # Streamlit Dashboard (4 trang)
│   └── eval/                 # Bootstrap CI, Groundedness check, Metrics
├── tests/                    # Toàn bộ unit tests & integration tests
├── docker/                   # Dockerfile cho api và ui
├── docker-compose.yml        # Điều phối 3 services (db, api, ui)
├── pyproject.toml            # Cấu hình pythonpath, pytest, ruff
├── requirements.txt          # Danh sách thư viện phụ thuộc
└── README.md                 # Hướng dẫn cài đặt & vận hành 1-click
```

---

## 6. Taxonomy 8 Khía Cạnh Đánh Giá (ABSA Taxonomy)

Hệ thống phân loại đánh giá khách hàng theo 8 khía cạnh chuẩn mực:
1. `WATERPROOF`: Khả năng chống thấm nước, độ kín đường may ép nhiệt, độ dày chống tràn nước.
2. `MATERIAL_DURABILITY`: Chất liệu vải (dù, PVC, tráng PU), độ bền, chống rách, độ bền nút/khóa kéo.
3. `FIT_SIZE`: Độ vừa vặn, kích cỡ chiều dài/chiều rộng, che phủ khi ngồi xe máy hoặc đeo balo.
4. `COMFORT_USABILITY`: Sự tiện dụng khi mặc/gấp, độ thoáng khí/hầm bí, kính chắn mưa, tay bao gương.
5. `PRICE_VALUE`: Giá cả tương xứng chất lượng, độ đáng tiền so với kỳ vọng.
6. `PACKAGING_SHIPPING`: Đóng gói túi/hộp, tốc độ giao hàng, thái độ shipper.
7. `CUSTOMER_SERVICE`: Thái độ hỗ trợ tư vấn của shop, tốc độ phản hồi tin nhắn, chính sách đổi trả hàng lỗi.
8. `ACCESSIBILITY_DESIGN`: Màu sắc, kiểu dáng thời trang, họa tiết, tính thẩm mỹ tổng thể.

---

## 7. Tiêu Chuẩn Kiểm Định Trước Khi Hoàn Tất Tác Vụ

Trước khi kết thúc bất kỳ phiên làm việc nào, bắt buộc thực hiện kiểm tra:
```bash
# 1. Chạy toàn bộ test tự động
pytest -v   # hoặc .venv\Scripts\pytest -v trên Windows

# 2. Kiểm tra chất lượng và định dạng mã nguồn
ruff check .               # hoặc .venv\Scripts\python -m ruff check .
ruff format . --check      # hoặc .venv\Scripts\python -m ruff format . --check
```
Tất cả các bài kiểm thử phải đạt **100% Passed** và **0 lỗi lint**.

---

## 8. Quy Tắc Hành Vi & Ghi Chú Bản Quyền (Credit Note)

- **Ngôn ngữ trao đổi:** Tiếng Việt (chính xác, trọng tâm, học thuật, tôn trọng).
- **Mã nguồn, comment:** Tiếng Anh chuyên nghiệp.
- **Quy tắc đặt tên Commit Git khi Push lên GitHub:**
  - *Nếu người dùng yêu cầu Agent tự tạo tên commit:* Bắt buộc viết bằng **tiếng Việt**, tuyệt đối **không** dùng định dạng tiền tố `abc: xyz` (không dùng `feat:`, `fix:`, `chore:`, ...), mà phải đi thẳng vào nội dung `xyz` (Ví dụ: `hoàn thiện 10 endpoint FastAPI, dashboard Streamlit 4 trang`).
  - *Nếu người dùng tự đặt tên commit:* Lấy chính xác 100% nguyên văn tên do người dùng đặt (không tự ý thêm tiền tố, dịch hoặc sửa đổi).
- **Credit Note bắt buộc:** Mọi file mới được tạo hoặc sửa đổi có ý nghĩa phải có chữ ký tác quyền ở dòng cuối:
  - File Python, Shell, YAML: `# CreBy: MenBoyBMN`
  - File Markdown, HTML: `<!-- CreBy: MenBoyBMN -->`

<!-- CreBy: MenBoyBMN -->
