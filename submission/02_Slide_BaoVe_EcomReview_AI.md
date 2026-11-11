# BỘ SLIDE THUYẾT TRÌNH BẢO VỆ ĐỒ ÁN: ECOMREVIEW AI (18 SLIDES CHÍNH + 6 BACKUP SLIDES)

---

## SLIDE 1: TRANG BÌA (TITLE SLIDE)
- **Đề tài:** **EcomReview AI** — Hệ Thống AI Agent Tự Động Phân Tích Phản Hồi Khách Hàng Tiếng Việt Theo Khía Cạnh (ABSA) Và Đề Xuất Hành Động Marketing Cho Doanh Nghiệp Nhỏ (SMEs)
- **Case Study thực tế:** Gian hàng Áo mưa thời trang & tiện lợi trên **Shopee & TikTok Shop**
- **Phiên bản:** `v1.0` (Full-Stack FastAPI + Streamlit + PostgreSQL/SQLite + Docker Compose 1-Click + Local AI Addon)

---

## SLIDE 2: BỐI CẢNH & NỖI ĐAU CỦA CHỦ SHOP NHỎ (PROBLEM STATEMENT)
- **Quá tải dữ liệu nhiễu trên Shopee & TikTok Shop:** Hàng trăm bình luận chứa teencode (`ko, dc, sp, sz`), không dấu, emoji và câu ghép phức tạp.
- **Điểm mù "Phàn nàn ẩn" (`Hidden Complaints`):** Khách vẫn chấm **4–5 sao** vì thương shipper/giao nhanh nhưng chê chất vải mỏng, mùi nhựa nồng hoặc ngấm nước đường may trong bình luận.
- **Thất bại của LLM một bước (`Single-Prompt Agent`):** Tự bịa đặt con số thống kê (`Numeric Hallucination`), khuyên chung chung hoặc vi phạm chính sách sàn (*"cam kết chống thấm 100%"*, *"tặng tiền đổi 5 sao"*).

---

## SLIDE 3: MỤC TIÊU NGHIÊN CỨU & 3 CÂU HỎI NGHIÊN CỨU (`RQ1 – RQ3`)
- **RQ1 (ABSA & Domain Shift):** So sánh 4 kiến trúc (`B1 Rule`, `B2 TF-IDF + LogReg`, `B3 ViSoBERT`, `A1-v2 Gemini Flash Structured Output`) trên miền công khai và miền Áo mưa ít mẫu.
- **RQ2 (Vietnamese Social Text Normalization):** Thực nghiệm cắt bỏ $4 \times 2$ đo tác động của bộ chuẩn hóa ngôn ngữ mạng lên từng kiến trúc mô hình trên các lát cắt nhiễu.
- **RQ3 (Evidence-Grounded Agent & HybridCritic R1–R7):** Chứng minh hiệu quả của `SQL/Wilson 95% CI Aggregator + Pure Python State-Graph + HybridCritic 7 Luật` so với `P0 Single-Prompt`.

---

## SLIDE 4: CHIẾN LƯỢC DỮ LIỆU KÉP & ĐỘ ĐỒNG THUẬN GÁN NHÃN ($\kappa = 0.8780$)
- **Track 1 (Public Benchmark UIT-ViSFD):** $N = 2.200$ mẫu (`1.500 train / 300 val / 400 test`) đảm bảo cỡ mẫu lớn để huấn luyện chuẩn mực `B2` và `B3`.
- **Track 2 (Real Shop Áo Mưa — 8 Khía cạnh):**
  - 8 khía cạnh: `WATERPROOF`, `MATERIAL_DURABILITY`, `FIT_SIZE`, `COMFORT_USABILITY`, `PRICE_VALUE`, `PACKAGING_SHIPPING`, `CUSTOMER_SERVICE`, `ACCESSIBILITY_DESIGN`.
  - Chia tách chống rò rỉ dữ liệu (`seed=42`): Tập `dev.jsonl` ($N=60$) và tập kiểm thử khóa cứng **`test_locked.jsonl` ($N=105$ mẫu thật 100%, khóa mã băm SHA-256)**.
  - Độ đồng thuận gán nhãn độc lập 2 lượt: **$\kappa_{\text{overall}} = 0.8780$**, **$\kappa_{\text{mean}} = 0.9241$** (*Almost Perfect Agreement*).

---

## SLIDE 5: PHÒNG THỦ ĐA TẦNG 4 LỚP & TIỀN XỬ LÝ NGÔN NGỮ MẠNG (`SECURITY & NORMALIZER`)
- **4 Lớp Bảo mật Chiều sâu (`Defense-in-Depth`):**
  1. Ẩn danh 100% SĐT/Email (`scrub_pii`) & khử khuẩn ký tự điều khiển (`sanitize_for_llm`).
  2. Cô lập văn bản khách hàng trong thẻ XML `<customer_review>...</customer_review>`.
  3. Ép kiểu đầu ra nghiêm ngặt qua Pydantic v2 `Structured Output` + hậu kiểm trích dẫn `_post_validate_evidence`.
  4. Cưỡng chế kết nối CSDL chỉ đọc (`read_only=True`) cho toàn bộ truy vấn phân tích của Agent.
- **Chuẩn hóa Teencode có kiểm soát ngữ cảnh (`normalize.py`):** Bảo vệ đơn vị tiền tệ (`150k -> 150 nghìn`), nén ký tự kéo dài, ánh xạ cảm xúc Emoji và chặn lỗi *Over-normalization* từ ghép (`"chất liệu"`, `"chat với shop"`).

---

## SLIDE 6: KIẾN TRÚC ZERO NUMERIC HALLUCINATION (`SQL AGGREGATOR + WILSON 95% CI`)
- **Nguyên tắc bất biến #1:** Tuyệt đối không để LLM tự đếm review hay tính phần trăm.
- **Khoảng tin cậy bất đối xứng Wilson Score 95% CI (`tools_aggregator.py`):** Khắc phục hoàn toàn hiện tượng suy biến của công thức Gauss trên cỡ mẫu nhỏ ($n \ge 5$).
- **5 Nhóm Nhận định Tự động (`InsightEngine`):** `TOP_PAIN`, `STRENGTH`, `HIDDEN_COMPLAINT` (bắt đánh giá 4–5 sao có ý kiến tiêu cực), `PLATFORM_GAP` (chênh lệch Shopee vs TikTok) và `EMERGING_ISSUE`.
- **Hậu kiểm số học tầng 1:** Hàm `verify_numbers_in_statement()` kiểm tra 100% con số trong câu nhận định với kết quả SQL (sai số số học = `0.0%`).

---

## SLIDE 7: ĐỒ THỊ TRẠNG THÁI THUẦN PYTHON & BỘ PHẢN BIỆN LAI (`HYBRID CRITIC R1–R7`)
- **Vòng lặp State-Graph (`graph_runner.py`):** `Aggregator -> InsightEngine -> ActionPlanner <-> HybridCritic (tối đa 2 retries) -> Deterministic Auto-Repair -> Human Approval Gate`.
- **7 Quy tắc Xác định R1–R7 (`critic.py`):**
  - `R1`: Dẫn chứng $\ge 2$ `evidence_review_ids` có thật trong DB & `insight_ids` hợp lệ.
  - `R2`: Số liệu trong `why_rationale` khớp 100% với SQL Insight.
  - `R3`: Đủ 4 trường (`What, Why, How/When, KPI`) kèm từ khóa thời hạn (`24h, 48h, ngày, tuần`).
  - `R4`: Cấm cam kết quá đà (*"chống thấm 100%"*, *"vĩnh viễn không rách"*).
  - `R5`: Đồng bộ cờ `is_marketing` (`PRODUCT_FIX / OPS` $\rightarrow$ `False`).
  - `R6`: Chống trùng lặp hành động (Jaccard $\le 0.80$).
  - `R7`: An toàn chính sách sàn (cấm *"tặng tiền đổi 5 sao"*, *"xóa đánh giá 1 sao"*).

---

## SLIDE 8: KIẾN TRÚC FULL-STACK 3 TẦNG (`FASTAPI 10 ENDPOINTS + STREAMLIT 4 TRANG + DOCKER`)
- **Backend FastAPI (`src/ecomreview/api/main.py`):** 10 RESTful Endpoints chuẩn OpenAPI 3.1, độ trễ `< 150 ms`.
- **Giao diện Streamlit Dashboard 4 Trang (`src/ecomreview/ui/app.py`):**
  - *Trang 1:* Tổng quan & Biểu đồ Plotly thanh sai số bất đối xứng Wilson 95% CI.
  - *Trang 2:* Khám phá đánh giá & Truy vết trích dẫn bằng chứng nguyên văn.
  - *Trang 3:* Kế hoạch hành động (tách biệt Marketing vs Vận hành) & Cổng duyệt `Approve / Edit / Reject`.
  - *Trang 4:* Nạp dữ liệu mới & Quan sát trực tiếp nhật ký kiểm định `HybridCritic` Trace JSON.
- **Đóng gói 1-Click (`docker-compose.yml`):** 3 containers (`db, api, ui`) tích hợp `DEMO_CACHE_MODE=true`.

---

## SLIDE 9: KẾT QUẢ THỰC NGHIỆM RQ1 — SO SÁNH 4 MÔ HÌNH ABSA (`TRACK 1 & TRACK 2`)
- **Trên tập kiểm thử khóa cứng `test_locked.jsonl` ($N = 105$, Shop Áo Mưa):**
  - `B1 (Rule & Lexicon)`: Overall F1 = `0.4187`, Aspect Det F1 = `0.8731`, Joint ABSA F1 = `0.5680`, Quote Fidelity = `93.5%`.
  - `B2 (TF-IDF + LogReg)`: Overall F1 = `0.5296`, Aspect Det F1 = `0.7683`, Joint ABSA F1 = `0.3835` *(Suy giảm mạnh do Domain Shift)*.
  - `B3 (ViSoBERT Cross-Domain)`: Overall F1 = `0.5296`, Aspect Det F1 = `0.6329`, Joint ABSA F1 = `0.3706` *(Suy giảm mạnh do Domain Shift)*.
  - **`A1-v2 (Gemini Flash Frozen)`:** Overall F1 = **`0.8248 [0.7324 - 0.8983]`**, Aspect Det F1 = **`0.9066`**, Joint ABSA F1 = **`0.6665 [0.5555 - 0.7718]`**, Quote Fidelity = **`97.4%`** ($p < 0.0001$).

---

## SLIDE 10: KẾT QUẢ THỰC NGHIỆM RQ2 — TÁC ĐỘNG CỦA CHUẨN HÓA NGÔN NGỮ MẠNG ($4 \times 2$)
- **Tăng tốc hiệu năng rõ rệt cho mô hình từ vựng/subword (`B2` & `B3`):**
  - `B3 (ViSoBERT)` tăng **`+4.04%`** Overall F1 toàn tập và tăng vọt **`+12.05%`** trên lát cắt `Slice_Emoji` (`0.4603 -> 0.5808`).
  - `B2 (TF-IDF)` tăng **`+4.37%`** trên `Slice_Teencode` (`0.5341 -> 0.5778`) và **`+17.69%`** trên `Slice_Emoji` (`0.4051 -> 0.5820`).
- **Kháng nhiễu tự nhiên của `A1-v2`:** Đạt `F1 = 1.0000` tuyệt đối trên văn bản không dấu (`Slice_NoDiacritics`).
- **Bài học kiến trúc:** Bật `norm=ON` (kèm `FIX_01` lookahead guard) cho `B1/B2/B3`, đồng thời giữ văn bản gốc `raw_text` song song cho `A1-v2` để bảo toàn 100% trích dẫn nguyên văn.

---

## SLIDE 11: KẾT QUẢ THỰC NGHIỆM RQ3 (PHẦN 1) — ĐÁNH GIÁ TỰ ĐỘNG & CẮT BỎ CRITIC
- **Đối sánh trên 10 kịch bản kinh doanh ($S_1 \dots S_{10}$, 2.000 Bootstrap resamples):**
  - **`P0_Single_Prompt`:** Evidence Validity = `0.0%`, Numeric Consistency = `0.0%`, Structural Completeness = `66.7%`, Policy Safety = `33.3%`, Điểm Critic = `1.00/5.0` (`0/10` đạt).
  - **`P1_No_Critic` (Vòng 0 khi tắt Critic):** Evidence Validity = `100.0%`, nhưng Numeric Consistency chỉ đạt **`51.67% [46.67 - 56.67]`** do tham chiếu chéo lệch chỉ mục khi có nhiều Insights.
  - **`P1_Full_Proposed` (Có `HybridCritic` R1–R7 & `Auto-Repair`):** Đạt tuyệt đối **`100.0%`** trên cả 5 chỉ số (`+48.33%` Numeric Consistency so với khi tắt Critic), Điểm Critic = **`5.00/5.0`**, Pass Rate = **`100.0% (10/10)`**.

---

## SLIDE 12: KẾT QUẢ THỰC NGHIỆM RQ3 (PHẦN 2) — CHẤM MÙ A/B & MÔ PHỎNG PHÊ DUYỆT
- **Chấm mù A/B theo Rubric 5 tiêu chí (`C1–C5`, thang 1.0–5.0):**
  - `P1_Full_Proposed` đạt **`4.98 / 5.00 [4.94 - 5.00]`** so với **`2.17 / 5.00`** của `P0` ($\Delta = +2.81$).
  - Chiến thắng tuyệt đối **`100.0% (10/10 kịch bản)`** trong thử nghiệm mù (`results/blind_ab_pack.md`).
- **Mô phỏng duyệt nghiệp vụ của Chủ shop SME (`29 đề xuất hành động`):**
  - `APPROVED` ngay lập tức (`edit_distance = 0`): **`89.66%` (26/29)**.
  - `EDITED` nhẹ (điều chỉnh trần ngân sách voucher): **`6.90%` (2/29)**.
  - `REJECTED` (tạm hoãn hành động chung `GENERAL`): **`3.45%` (1/29)**.
  - **Tổng tỷ lệ chấp nhận sử dụng (`Usable Adoption`):** **`96.55%` (28/29)**.

---

## SLIDE 13: CASE STUDY THỰC TẾ TRÊN GIAN HÀNG ÁO MƯA (`REAL_SHOP` — 150 ĐÁNH GIÁ)
- **Phát hiện 3 điểm mù lớn từ dữ liệu thực:**
  1. `TOP_PAIN`: Khía cạnh `WATERPROOF` chịu tỷ lệ phàn nàn `50.0% [29.0% - 71.0%]` (ngấm nước đường may đáy quần).
  2. `HIDDEN_COMPLAINT`: Bóc tách **23 phàn nàn ẩn (`17.0%`)** nằm trong 135 đánh giá 4–5 sao.
  3. `PLATFORM_GAP`: Chênh lệch trải nghiệm **`47.3%`** giữa Shopee (`55.6%` tiêu cực) và TikTok Shop (`8.3%` tiêu cực).
- **Hiệu quả vận hành:** Cả 5 đề xuất (`act_001`..`act_005`) đều được duyệt triển khai, rút ngắn thời gian phân tích & lập kế hoạch từ **~135–180 phút làm thủ công xuống còn ~5 phút (~95% thời gian tiết kiệm)**.

---

## SLIDE 14: PHÂN TÍCH LỖI HỆ THỐNG THEO QUY LUẬT PARETO (`E1 – E10`)
- **Tổng số 136 ca lỗi phân loại vào 10 nhóm chuẩn (`results/error_taxonomy.csv`):**
  - **Nhóm Vital Few (5 nhóm đầu chiếm đúng `80.15%` = 109/136 lỗi):**
    1. `E6` — Suy giảm do Chuyển miền ở B2/B3 (`27.94%`).
    2. `E1` — Nhầm ranh giới khía cạnh `WATERPROOF` vs `MATERIAL_DURABILITY` (`17.65%`).
    3. `E2` — Đảo cực câu ghép đối lập *"Tuy... nhưng..."* & phàn nàn ẩn (`13.97%`).
    4. `E8` — Ảo giác số học ở P0 & lệch chỉ mục trước Critic (`11.76%`).
    5. `E4` — Over-normalization từ ghép Teencode (`8.82%`).
- **Cải tiến Hậu kiểm (`Post-Hoc Fixes`):** `FIX_01` (`normalize.py`), `FIX_02` (`HybridCritic R2`), `FIX_03` (`analyzer_v2_frozen.md`) đều được kiểm chứng qua `tests/test_regression.py`.

---

## SLIDE 15: MINH HỌA GIAO DIỆN STREAMLIT DASHBOARD 4 TRANG & DEMO VIDEO
- **Trải nghiệm khép kín từ Dữ liệu thô $\rightarrow$ Quyết định kinh doanh:**
  - *Trang 1:* Biểu đồ thanh sai số bất đối xứng Wilson 95% CI & 5 nhóm Insights.
  - *Trang 2:* Bộ lọc đa chiều & kiểm chứng câu trích dẫn nguyên văn đã ẩn danh PII.
  - *Trang 3:* Thẻ hành động 4 thành phần (`What, Why, How/When, KPI`) & nút duyệt `Approve / Edit / Reject`.
  - *Trang 4:* Upload đánh giá mới & Trình khám phá nhật ký `HybridCritic` Trace JSON.

---

## SLIDE 16: BẢN MỞ RỘNG ADDON 11 (`v1.1-addon`) — TÍCH HỢP LOCAL AI (`OLLAMA + QWEN2.5-7B`)
- **Kiến trúc Đa Nhà Cung Cấp (`UnifiedLLMClient` trong `src/ecomreview/llm_provider.py`):**
  - Chuyển đổi trực tiếp giữa **Cloud API (`Gemini Flash`)** và **Local AI (`Ollama Qwen2.5-7B`)** ngay trên thanh công cụ Sidebar của Dashboard.
  - Tích hợp cơ chế **Self-Healing JSON Retry** (tối đa 2 lần tự sửa lỗi Pydantic Schema cho model 7B).
- **Từ điển Mở YAML (`knowledge/vn_social_lexicon.yaml`):** Cho phép chủ shop tự bổ sung từ lóng mới mà không cần sửa code Python.
- **Kết quả đối sánh Cloud vs Local:** Nhờ SQL Aggregator + `HybridCritic` R1–R7, ngay cả model 7B chạy nội bộ miễn phí vẫn đạt **100.0% Numeric Consistency & Groundedness**.

---

## SLIDE 17: TỔNG KẾT ĐÁP ỨNG 12/12 YÊU CẦU ĐỀ BÀI & ĐÓNG GÓP
- **Hoàn thành 100% (12/12 hạng mục bàn giao):**
  - Báo cáo nghiên cứu 40 trang, 22 công trình trích dẫn có DOI, Dataset kép khóa SHA-256 ($\kappa = 0.8780$), 3 Baselines (`B1, B2, B3`), Mô hình & Agent đề xuất (`A1-v2 & P1`), Phân tích lỗi Pareto `E1–E10`, Source code (`60+ tests passed 100%, ruff 0 lỗi`), Docker Compose 1-click, Dashboard 4 trang + FastAPI 10 endpoints, Video Demo 1080p, Tài liệu Kiến trúc/API, và Đánh giá tam giác RQ3.

---

## SLIDE 18: HẠN CHẾ, HƯỚNG PHÁT TRIỂN & LỜI CẢM ƠN
- **Hướng phát triển tiếp theo:**
  1. Mở rộng kho Playbook đa ngành hàng (`Mỹ phẩm, Thời trang, Gia dụng`).
  2. Tích hợp phân tích Đa phương thức (`Multimodal Text + Image + Video feedback`).
  3. Tự động hóa khép kín qua **Shopee / TikTok Open Platform API** sau khi chủ shop nhấn `Approve`.
- **Xin trân trọng cảm ơn Hội đồng chấm đồ án! Sẵn sàng trả lời các câu hỏi phản biện.**

---

## PHỤ LỤC DỰ PHÒNG HỎI ĐÁP (6 BACKUP SLIDES: `B1 – B6`)

### BACKUP SLIDE B1: CHI TIẾT MA TRẬN ÁNH XẠ KHÍA CẠNH 2 TẦNG (`TWO-TIER ASPECT PROTOCOL`)
- Ánh xạ chính xác giữa 8 `FineAspect` ngành Áo mưa và 4 `MacroAspect` chung của TMĐT (`PERFORMANCE_FUNCTION`, `QUALITY_DESIGN`, `PRICE_VALUE`, `SERVICE_LOGISTICS`) kèm bộ phân loại an toàn `SafeAspectClassifier` cho các lớp hiếm.

### BACKUP SLIDE B2: CÔNG THỨC TOÁN HỌC WILSON SCORE 95% CI & CLUSTER BOOTSTRAP
- Công thức bất đối xứng Wilson Score:
  $$\frac{\hat{p} + \frac{z^2}{2n} \pm z \sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}, \quad z = 1.95996$$
- Công thức điểm ưu tiên: $\text{Priority} = \frac{W_{\text{impact}} \times (1 + \text{Severity\%}/100) \times W_{\text{conf}}}{W_{\text{effort}}}$.

### BACKUP SLIDE B3: CHI TIẾT 10 CA TIÊM LỖI KIỂM ĐỊNH `HYBRID CRITIC` (`FAULT INJECTION`)
- Bắt trúng 10/10 lỗi tiêm thử nghiệm (`tests/test_critic.py`): sai `insight_id` (R1), thiếu mã review (R1), bịa tỷ lệ `87.5%` (R2), bịa số đếm `95/100` (R2), thiếu thời hạn (R3), nội dung cụt lủn (R3), cam kết *"chống thấm 100%"* (R4), lệch cờ `is_marketing` (R5), trùng lặp Jaccard $> 0.80$ (R6), gạ *"tặng tiền đổi 5 sao"* (R7).

### BACKUP SLIDE B4: SƠ ĐỒ QUAN HỆ THỰC THỂ 6 BẢNG CSDL & CHẾ ĐỘ `READ-ONLY ISOLATION`
- 6 bảng: `reviews`, `opinions`, `insights`, `actions`, `action_feedback`, `system_jobs_audit`. Tiến trình phân tích của Agent luôn chạy dưới cờ `read_only=True` (`PRAGMA query_only = ON` / `SET TRANSACTION READ ONLY`).

### BACKUP SLIDE B5: DANH SÁCH ĐẦY ĐỦ 10 RESTFUL ENDPOINTS TRÊN FASTAPI (`OPENAPI 3.1`)
- `GET /health`, `POST /reviews/upload`, `POST /analyze/run`, `GET /jobs/{id}`, `GET /stats/overview`, `GET /insights`, `POST /actions/generate`, `GET /actions`, `POST /actions/{id}/decision`, `GET /reviews`.

### BACKUP SLIDE B6: CHI TIẾT ĐỐI SÁNH CLOUD GEMINI FLASH VS LOCAL OLLAMA QWEN2.5-7B (`ADDON 11`)
- Bảng thực nghiệm `results/addon_local_vs_cloud.csv`: Mặc dù `Qwen2.5-7B` có độ trễ suy luận cục bộ cao hơn, nhờ kiến trúc tách biệt `SQL Aggregator + HybridCritic R1–R7`, độ nhất quán số học (`Numeric Consistency`) và độ hợp lệ bằng chứng (`Evidence Validity`) của cả hai chế độ đều đạt **100.0%**.

<!-- CreBy: MenBoyBMN -->
