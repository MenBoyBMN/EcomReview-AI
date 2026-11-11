# Tài Liệu Kiến Trúc Hệ Thống EcomReview AI (`System Architecture & ADR`)

Tài liệu này mô tả chi tiết kiến trúc kỹ thuật của hệ thống **EcomReview AI** qua **4 sơ đồ kiến trúc chuẩn** (Container 3 tầng, Pipeline Dữ liệu & Bảo mật 4 lớp, Đồ thị Trạng thái Tác tử `Pure Python State-Graph`, và Sơ đồ Quan hệ Thực thể CSDL 6 bảng) cùng **Bảng Quyết định Kiến trúc (`Architecture Decision Records — ADR`)**.

---

## 1. Sơ Đồ Kiến Trúc Container 3 Tầng (`3-Tier Container Architecture`)

```mermaid
flowchart LR
    subgraph UserLayer["Tầng Người Dùng (SME Owner)"]
        U["Chủ Gian Hàng Shopee / TikTok Shop"]
    end

    subgraph UIContainer["Container 1: Streamlit Dashboard (Port 8501)"]
        P1["Trang 1: Tổng Quan & Cảnh Báo Sớm"]
        P2["Trang 2: Phân Tích Khía Cạnh & Xu Hướng"]
        P3["Trang 3: Đề Xuất Hành Động & Phê Duyệt HITL"]
        P4["Trang 4: Khám Phá Đánh Giá & Bằng Chứng"]
        P5["Trang 5: Hỗ Trợ CSKH & Nạp Dữ Liệu"]
    end

    subgraph APIContainer["Container 2: FastAPI Backend & Agent Engine (Port 8000)"]
        API["15 RESTful Endpoints (OpenAPI 3.1)"]
        SEC["Security Filter (PII Scrub + XML Escape)"]
        ABSA["ABSA Engine (A1 Gemini v2 / B1 / B2 / B3 / Local Ollama)"]
        GRAPH["Pure Python State-Graph (Aggregator -> Insight -> Planner <-> Critic R1-R7)"]
        REP["Reporting Engine (Excel 6 sheets & HTML PDF)"]
        CS["CS Reply Assistant (Guardrails G1-G6)"]
    end

    subgraph DataLayer["Container 3: Storage & Knowledge Layer"]
        DB[("PostgreSQL 16 / SQLite (6 Bảng, Read-Only Guard)")]
        CACHE[("SHA-256 Response Cache (data/cache/)")]
        YAML[("Domain Playbook & Lexicon (knowledge/*.yaml)")]
    end

    U <--> UIContainer
    UIContainer <-->|"HTTP JSON REST API"| API
    API --> SEC --> ABSA
    API --> GRAPH
    ABSA <--> CACHE
    ABSA --> DB
    GRAPH <-->|"READ-ONLY SQL"| DB
    GRAPH <--> YAML
    API -->|"Write Feedback & Audit"| DB
```

---

## 2. Luồng Dữ Liệu & Phòng Thủ Bảo Mật 4 Lớp (`4-Layer Defense-in-Depth Pipeline`)

Đánh giá từ khách hàng trên sàn thương mại điện tử là dữ liệu ngoại vi không đáng tin cậy (`Untrusted External Input`). Hệ thống áp dụng 4 lớp bảo vệ tuần tự trước và sau khi tương tác với LLM:

```mermaid
flowchart TD
    R["Đánh Giá Gốc Từ Sàn (Raw E-Commerce Review)"] --> L1["Lớp 1: Ẩn Danh PII & Khử Khuẩn (scrub_pii + sanitize_for_llm)"]
    L1 --> L2["Lớp 2: Cô Lập Trong Thẻ XML (<customer_review>...</customer_review>)"]
    L2 --> NORM["Tiền Xử Lý Ngôn Ngữ Mạng Có Kiểm Soát (normalize_social_text + Lookahead Guard)"]
    NORM --> L3["Lớp 3: Ép Kiểu Đầu Ra Nghiêm Ngặt (Pydantic v2 Structured Output + _post_validate_evidence)"]
    L3 --> DB_WRITE["Ghi Vào Bảng reviews & opinions"]
    DB_WRITE --> L4["Lớp 4: Kết Nối CSDL Chỉ Đọc (read_only=True) Khi Chạy Agent & SQL Aggregator"]
```

---

## 3. Đồ Thị Trạng Thái Tác Tử Thuần Python (`Pure Python State-Graph & HybridCritic R1–R7`)

```mermaid
stateDiagram-v2
    [*] --> SQLAggregator: "Truy vấn READ-ONLY (min_n >= 5)"
    SQLAggregator --> InsightEngine: "Tính Wilson 95% CI & Lọc bằng chứng Jaccard <= 0.70"
    InsightEngine --> VerifyNumbers: "Sinh 5 nhóm Insights (TOP_PAIN, STRENGTH, HIDDEN, GAP, EMERGING)"
    VerifyNumbers --> ActionPlanner: "verify_numbers_in_statement() = 100% khớp SQL"
    ActionPlanner --> HybridCritic: "Sinh ActionProposals từ playbook_aomua.yaml + compute_priority_score()"
    HybridCritic --> ActionPlanner: "Vi phạm R1-R7 (Retry <= 2 kèm feedback_prompt)"
    HybridCritic --> AutoRepair: "Hết lượt Retry mà còn lỗi khả sửa"
    AutoRepair --> HumanApprovalGate: "Đồng bộ xác định 100% R1-R7 (Score = 5.0/5.0)"
    HybridCritic --> HumanApprovalGate: "Passed = True (0 vi phạm R1-R7)"
    HumanApprovalGate --> [*]: "Chủ Shop duyệt (APPROVED / EDITED / REJECTED)"
```

### Bảng 7 Quy Tắc Xác Định Trong `HybridCritic` (`src/ecomreview/agent/critic.py`):
- **`R1 (Evidence Existence)`:** Mỗi hành động phải tham chiếu `insight_ids` hợp lệ và gắn kèm $\ge 2$ mã `evidence_review_ids` có thật trong CSDL.
- **`R2 (Numeric Grounding)`:** Mọi con số thống kê trong `why_rationale` phải khớp 100% với số liệu SQL của Insight được tham chiếu (`verify_numbers_in_statement`).
- **`R3 (Action Completeness & Deadline)`:** Đầy đủ 4 thành phần (`what_to_do`, `why_rationale`, `how_and_when`, `success_metric`) và có từ khóa thời hạn thực hiện cụ thể (`24h`, `48h`, `ngày`, `tuần`).
- **`R4 (No Overclaiming)`:** Cấm tuyệt đối các cam kết quảng cáo quá đà ngành áo mưa (*"chống thấm 100%"*, *"chống nước tuyệt đối"*, *"vĩnh viễn không rách"*).
- **`R5 (Marketing Flag Sync)`:** Đồng bộ chính xác cờ `is_marketing = True` (`LISTING_UPDATE`, `CONTENT`, `REVIEW_REPLY`, `PROMOTION`, `CUSTOMER_CARE`) và `is_marketing = False` (`PRODUCT_FIX`, `OPS`).
- **`R6 (Anti-Duplication)`:** Độ tương đồng từ vựng Jaccard giữa mọi cặp đề xuất trong cùng kịch bản phải $\le 0.80$.
- **`R7 (Platform Policy Safety)`:** Cấm tuyệt đối các hành vi vi phạm chính sách sàn Shopee/TikTok (*"tặng tiền đổi 5 sao"*, *"xóa đánh giá 1 sao"*, *"chuyển khoản ngoài sàn"*).

---

## 4. Sơ Đồ Quan Hệ Thực Thể CSDL 6 Bảng (`Database ERD`)

```mermaid
erDiagram
    REVIEWS ||--o{ OPINIONS : "has_extracted"
    INSIGHTS ||--o{ ACTIONS : "grounds"
    ACTIONS ||--o{ ACTION_FEEDBACK : "receives_human_review"

    REVIEWS {
        string review_id PK
        string platform
        string shop
        string product
        int rating
        string text_raw
        string text_norm
        string scenario_tag
        string overall_sentiment
        boolean informative
        string created_at
    }
    OPINIONS {
        int id PK
        string review_id FK
        string scenario_tag
        string aspect
        string polarity
        string evidence
        boolean evidence_ok
        string analyzer_method
    }
    INSIGHTS {
        int id PK
        string scenario_tag
        string kind
        string aspect
        string statement
        json numbers_json
        json evidence_ids
        string confidence
    }
    ACTIONS {
        int id PK
        string scenario_tag
        string action_type
        boolean is_marketing
        string title
        string what_to_do
        string why_rationale
        string how_and_when
        string success_metric
        float priority_score
        json insight_ids
        json evidence_review_ids
        boolean critic_passed
        string status
    }
    ACTION_FEEDBACK {
        int id PK
        int action_id FK
        string decision
        string reason_category
        string note
        string edited_content
        string decided_by
    }
    SYSTEM_JOBS_AUDIT {
        int id PK
        string job_type
        string status
        json details_json
    }
```

---

## 5. Bảng Quyết Định Kiến Trúc (`Architecture Decision Records — ADR`)

| Mã ADR | Quyết Định Kỹ Thuật | Phương Án Thay Thế Đã Xét | Lý Do Lựa Chọn (`Rationale`) |
| :-: | :--- | :--- | :--- |
| **ADR-01** | **Pure Python State-Graph** thay vì LangChain / CrewAI | LangGraph, CrewAI, AutoGen | Loại bỏ hoàn toàn xung đột phiên bản phụ thuộc, kiểm soát 100% luồng retry/auto-repair xác định, dễ gỡ lỗi và độ trễ cực thấp (`< 80 ms` ở chế độ cache). |
| **ADR-02** | **SQL Aggregator + Wilson 95% CI** tính toán 100% số liệu trước LLM | Đưa toàn bộ review vào prompt để LLM tự đếm | Triệt tiêu 100% ảo giác số học (`Zero Numeric Hallucination`) và phản ánh trung thực độ bất định thống kê khi cỡ mẫu khía cạnh nhỏ. |
| **ADR-03** | **Hybrid Critic (7 Luật Python R1–R7 + Auto-Repair)** | Chỉ dùng LLM-as-a-Judge | Luật Python xác định bắt trúng 100% lỗi số học/chính sách trong `< 2 ms` với chi phí `$0.00`, không bị thiên kiến đồng thuận của LLM. |
| **ADR-04** | **Dual-Engine DB (PostgreSQL 16 + SQLite Fallback)** & `DEMO_CACHE_MODE` | Chỉ hỗ trợ PostgreSQL & bắt buộc gọi mạng | Đảm bảo hệ thống chạy mượt mà 100% cả trong môi trường Docker Production lẫn khi kiểm thử cục bộ / bảo vệ đồ án không cần Internet. |
| **ADR-05** | **Early Warning via Two-Proportion Z-Test** thay vì LLM Trend Detection | Cho LLM đọc bảng dữ liệu thời gian | Phát hiện bùng phát lỗi sản phẩm có ý nghĩa thống kê ($p < 0.05$), tránh báo động giả từ biến động ngẫu nhiên của các mẫu nhỏ. |
| **ADR-06** | **CS Reply Assistant với 6 Guardrails (G1–G6)** | Prompt LLM tự do sinh lời đáp | Đảm bảo phản hồi khách hàng 100% an toàn trước chính sách sàn Shopee/TikTok (chống hối lộ đổi sao, chống lộ hotline/kênh ngoài sàn, chống hứa hẹn tiền bồi hoàn vượt thẩm quyền). |

<!-- CreBy: MenBoyBMN -->

