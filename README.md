# 🌧️ EcomReview AI: Hệ Thống AI Agent Tự Động Phân Tích Phản Hồi Khách Hàng Tiếng Việt & Lập Kế Hoạch Hành Động Cho SMEs

**EcomReview AI** là hệ thống phân tích cảm xúc theo khía cạnh (**Aspect-Based Sentiment Analysis — ABSA**) kết hợp **Kiến trúc Tác tử Đồ thị Trạng thái Thuần Python (`Pure Python State-Graph`)** và **Bộ Phản biện Lai 7 Quy tắc (`HybridCritic` R1–R7)**, giúp các hộ kinh doanh và doanh nghiệp vừa và nhỏ (SMEs) trên **Shopee & TikTok Shop** chuyển hóa hàng trăm đánh giá khách hàng thành các đề xuất hành động Marketing / Vận hành có căn cứ thực tế và an toàn chính sách 100%.

---

## 🌟 5 Nguyên Tắc Kiến Trúc Bất Biến (`Architectural Invariants`)

1. **Zero Numeric Hallucination (Không Ảo Giác Số Học):** 100% số liệu thống kê, tỷ lệ phần trăm và khoảng tin cậy bất đối xứng **Wilson 95% CI** được tính toán bằng truy vấn SQL/Python (`tools_aggregator.py`) và hậu kiểm qua `verify_numbers_in_statement()` + Luật `R2`.
2. **Grounded & Actionable Proposals:** Mọi đề xuất hành động (`ActionProposal`) bắt buộc gắn kèm `insight_ids` hợp lệ và tối thiểu **2 mã đánh giá thực tế (`evidence_review_ids`)** từ CSDL.
3. **4-Layer Defense-in-Depth Security:** Ẩn danh SĐT/Email (`scrub_pii`), khử khuẩn chuỗi + bọc thẻ `<customer_review>`, ép kiểu đầu ra qua Pydantic v2 `Structured Output`, và cưỡng chế kết nối CSDL chỉ đọc (`read_only=True`) cho tiến trình phân tích.
4. **Pure Python State-Graph & HybridCritic (`R1–R7`):** Vòng lặp `Aggregator -> InsightEngine -> ActionPlanner <-> HybridCritic (R1–R7) -> Auto-Repair -> Human Approval Gate`.
5. **Scientific Reproducibility & Offline Cache Mode:** Cố định `seed=42`, khóa mã băm `SHA-256` cho tập kiểm thử `test_locked.jsonl`, kiểm định Bootstrap 95% CI, Cohen's Kappa ($\kappa = 0.8780$) và hỗ trợ `DEMO_CACHE_MODE=true` (chạy mượt 100% ngay cả khi không có Internet hoặc API Key).

---

## 🚀 Hướng Dẫn Khởi Chạy Nhanh 1-Click (`Quick Start`)

### Cách 1: Khởi chạy bằng Docker Compose (Khuyên dùng khi Demo / Triển khai)
```bash
# 1. Sao chép file cấu hình môi trường (mặc định bật sẵn DEMO_CACHE_MODE=true)
cp .env.example .env

# 2. Khởi chạy đồng thời 3 dịch vụ (PostgreSQL 16 + FastAPI Backend + Streamlit UI)
docker compose up --build -d
```
- **Giao diện Streamlit Dashboard (5 trang):** `http://localhost:8501`
- **Tài liệu tương tác FastAPI Swagger UI (15 Endpoints):** `http://localhost:8000/docs`
- **Tích hợp PostgreSQL 16 hoặc SQLite:** Tự động chuyển đổi qua `ECOMREVIEW_DB_BACKEND=postgres|sqlite`

### Cách 2: Khởi chạy trên Môi trường Python Cục bộ (`Local Virtualenv`)
```powershell
# 1. Kích hoạt môi trường ảo và cài đặt thư viện
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2. Khởi tạo CSDL mẫu (nạp 150 đánh giá real_shop + 10 kịch bản S1..S10)
python scripts/seed_demo.py
python scripts/backfill_review_dates.py

# 3. Khởi chạy FastAPI Backend (Terminal 1) và Streamlit Dashboard (Terminal 2)
python -m uvicorn ecomreview.api.main:app --port 8000
python -m streamlit run src/ecomreview/ui/app.py --server.port 8501
```

---

## 🛡️ Xác Thực & Bảo Mật API
FastAPI hỗ trợ xác thực header qua `X-API-Key` (mặc định chấp nhận key cấu hình tại `ECOMREVIEW_API_KEY` hoặc `demo-key-12345` khi chạy local/demo) và định danh người duyệt qua `X-Reviewer` (ví dụ `chu_shop_aomua`).

## 📊 5 Trang Dashboard Streamlit & Tính Năng Mới
1. **Trang 1 — Tổng quan & Cảnh báo Sớm:** Tỷ lệ hài lòng, Wilson 95% CI, banner cảnh báo sớm (`two-proportion z-test`).
2. **Trang 2 — Phân tích Khía cạnh & Xu hướng:** Biểu đồ xu hướng Plotly theo thời gian thực và so sánh Shopee vs TikTok Shop.
3. **Trang 3 — Đề xuất Hành động & Phê duyệt:** Duyệt `Approve / Edit / Reject`, truy vết `decided_by` và đo lường can thiệp (`Intervention Impact`).
4. **Trang 4 — Tra cứu Đánh giá & Bằng chứng:** Lọc bằng chứng, trích dẫn khách hàng và xem vết phân tích `ReviewAnalysis`.
5. **Trang 5 — Hỗ Trợ CSKH & Nạp Dữ Liệu:** Trợ lý phản hồi khách hàng tuân thủ 6 Guardrails (`G1–G6`), nạp file CSV/Excel kéo-thả, và xuất Báo cáo Điều hành Excel 6 sheet (`.xlsx`) & HTML in ra PDF.

---

## 🔬 Tái Lập Kết Quả Thực Nghiệm Nghiên Cứu (`RQ1, RQ2, RQ3 & Error Analysis`)

```powershell
# 1. Tái lập kết quả RQ1 (So sánh B1, B2, B3, A1-v2) & RQ2 (Ablation chuẩn hóa 4x2)
python -m ecomreview.eval.run_rq1_rq2

# 2. Tái lập kết quả RQ3 (Đo Groundedness tự động, Chấm mù A/B Rubric C1-C5 & Adoption)
python scripts/make_blind_eval.py

# 3. Tái lập phân tích lỗi Pareto (E1-E10) và xuất 4 biểu đồ PNG 300 DPI
python scripts/analyze_errors_and_figures.py

# 4. Chạy toàn bộ bộ kiểm thử tự động & kiểm tra chất lượng code
pytest -v
python -m ruff check .
python -m ruff format . --check
```

---

## 📂 Tài Liệu Kỹ Thuật & Báo Cáo Nghiên Cứu
- **Kiến trúc hệ thống & ADR:** [`docs/architecture.md`](docs/architecture.md)
- **Đặc tả 15 RESTful API Endpoints:** [`docs/api_reference.md`](docs/api_reference.md) và [`docs/openapi.json`](docs/openapi.json)
- **Phân tích lỗi Pareto `E1–E10`:** [`docs/error_analysis.md`](docs/error_analysis.md)
- **Case Study thực tế Shop Áo Mưa:** [`docs/case_study_shop_aomua.md`](docs/case_study_shop_aomua.md)
- **Báo cáo toàn văn & Slide bảo vệ:** Thư mục [`submission/`](submission/)

<!-- CreBy: MenBoyBMN -->
