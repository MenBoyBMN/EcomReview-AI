# Bộ Nhớ Ngữ Cảnh Dự Án (Project Memory Context)

Tài liệu này lưu trữ trạng thái tiến độ, kiến trúc cốt lõi, danh sách mốc quan trọng và theo dõi xuyên suốt 10 tuần phát triển của **EcomReview AI**.

---

## 1. Thông Tin Nhận Diện Dự Án
- **Tên Dự Án:** EcomReview AI
- **Chủ Đề:** Hệ thống AI Agent tự động phân tích phản hồi khách hàng tiếng Việt và đề xuất hành động marketing cho doanh nghiệp nhỏ.
- **Đối Tượng Thực Nghiệm:** Sản phẩm Áo mưa tiện lợi/thời trang trên Shopee và TikTok Shop.
- **Tiêu Chuẩn Đạt Được:** 12 yêu cầu kỹ thuật & học thuật (Báo cáo 30–50 trang, 3 Baselines, Đánh giá mù A/B, Docker Compose, Streamlit UI, Video demo).

---

## 2. Ba Mốc Kiểm Tra Trọng Yếu (Critical Milestones)

| Mốc | Thời Điểm | Mục Tiêu & Tiêu Chí Nghiệm Thu | Trạng Thái |
| :---: | :---: | :--- | :---: |
| **Mốc 1** | Hết Tuần 4 | Hoàn tất dữ liệu vàng, 3 Baselines (Rule, TF-IDF, ViSoBERT), Gemini Flash Analyzer, bảng thực nghiệm RQ1 (Macro F1) và RQ2 (Ablation teencode/chuyển miền). Nháp xong Chương 1 & 2. | ⏳ Chờ triển khai |
| **Mốc 2** | Hết Tuần 6 | Hoàn thành PostgreSQL, Aggregator, Insight Engine, Playbook tri thức miền Áo mưa, Planner & Hybrid Critic (7 luật xác định + LLM Judge), State-Graph Orchestrator chạy E2E có lưu trace logs. Nháp xong Chương 3. | ⏳ Chờ triển khai |
| **Mốc 3** | Hết Tuần 8 | Hoàn tất FastAPI backend, Streamlit Dashboard 4 trang, Docker Compose 1-click, Đánh giá mù RQ3 (10 kịch bản P0 vs P1), đo Groundedness & Actionability. Nháp xong Chương 4. | ⏳ Chờ triển khai |

---

## 3. Theo Dõi Tiến Độ Chi Tiết Theo 10 Tuần

- [ ] **Tuần 1:** Khởi động, chốt phạm vi nghiên cứu (RQ1–RQ3), cấu trúc repo, Pydantic schemas, lớp bảo vệ `security.py`, thu thập dữ liệu kép (Shop Áo Mưa + UIT-ViSFD).
- [ ] **Tuần 2:** Tiền xử lý tiếng Việt, từ điển teencode, gán nhãn dữ liệu tập vàng (Cohen's Kappa $\ge 0.70$), tổng quan 20 công trình liên quan (Chương 2).
- [ ] **Tuần 3:** Khung đánh giá thống kê (Macro F1, Bootstrap CI 95%), Baselines B1 (Rule) & B2 (TF-IDF + Logistic Regression), Gemini Flash Analyzer A1.
- [ ] **Tuần 4:** Fine-tune ViSoBERT B3 trên Colab T4, ablation study teencode/chuyển miền $\rightarrow$ **Nghiệm thu Mốc 1**.
- [ ] **Tuần 5:** PostgreSQL 16 schema, Aggregator SQL/Python (Wilson score, không ảo giác), Insight Engine tự động nhận diện xu hướng & bất thường.
- [ ] **Tuần 6:** Tri thức miền `playbook_aomua.yaml`, Action Planner, Hybrid Critic (R1–R7 + LLM Judge), State-Graph Orchestrator $\rightarrow$ **Nghiệm thu Mốc 2**.
- [ ] **Tuần 7:** FastAPI REST API, Streamlit Dashboard 4 trang kèm duyệt đề xuất, đóng gói Docker Compose (`db`, `api`, `ui`).
- [ ] **Tuần 8:** Đánh giá thực nghiệm RQ3: Quy trình mô phỏng, chấm mù A/B P0 vs P1, đo lường Groundedness & Feasibility $\rightarrow$ **Nghiệm thu Mốc 3**.
- [ ] **Tuần 9:** Phân tích lỗi hệ thống Pareto (80/20), tài liệu kiến trúc C4 & OpenAPI, kiểm tra triển khai máy sạch, quay video demo 5–10 phút.
- [ ] **Tuần 10:** Hợp nhất báo cáo nghiên cứu 30–50 trang (5 chương), slide thuyết trình bảo vệ (15–20 slide), ngân hàng 30 câu hỏi phản biện, đóng gói nghiệm thu.

---

## 4. Các Tham Số Cố Định Hệ Thống
- `RANDOM_SEED = 42`
- `CONFIDENCE_LEVEL = 0.95` (Bootstrap Iterations $B = 1000$)
- `KAPPA_THRESHOLD = 0.70`
- `LLM_MODEL = "gemini-2.5-flash"` (hoặc phiên bản flash ổn định tương đương qua `google-genai`)
- `CRITIC_MAX_RETRIES = 2`

<!-- CreBy: MenBoyBMN -->

