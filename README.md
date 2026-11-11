# 🌧️ EcomReview AI — Backend API & AI Engine

**EcomReview AI** là hệ thống Backend API & AI Engine chuyên sâu về phân tích cảm xúc theo khía cạnh (**Aspect-Based Sentiment Analysis — ABSA**) và tự động hóa lập kế hoạch hành động Marketing / Vận hành cho các doanh nghiệp thương mại điện tử (Shopee, TikTok Shop).

Hệ thống được thiết kế theo kiến trúc **Pure Backend Service**, sẵn sàng phục vụ bất kỳ ứng dụng Frontend hiện đại nào (Next.js, React, Vue, Mobile App) thông qua **15 RESTful API Endpoints**, tài liệu tương tác Swagger UI / OpenAPI 3.1 và cơ chế xác thực bảo mật `X-API-Key`.

---

## 🌟 5 Nguyên Tắc Kiến Trúc Bất Biến (`Architectural Invariants`)

1. **Zero Numeric Hallucination (Không Ảo Giác Số Học):** 100% số liệu thống kê, tỷ lệ phần trăm và khoảng tin cậy bất đối xứng **Wilson 95% CI** được tính toán xác thực qua SQL/Python (`tools_aggregator.py`) trên kết nối chỉ đọc (`READ-ONLY`) và kiểm thực chặt chẽ qua `verify_numbers_in_statement()`.
2. **Grounded & Actionable Proposals:** Mọi đề xuất hành động (`ActionProposal`) bắt buộc gắn kèm `insight_ids` hợp lệ và tối thiểu **2 mã đánh giá thực tế (`evidence_review_ids`)** từ CSDL làm bằng chứng.
3. **4-Layer Defense-in-Depth Security:** Ẩn danh SĐT/Email (`scrub_pii`), khử khuẩn chuỗi + bọc thẻ XML `<customer_review>`, ép kiểu đầu ra qua Pydantic v2 `Structured Output`, và khóa quyền CSDL chỉ đọc (`read_only=True`) cho các tác vụ phân tích.
4. **Pure Python State-Graph & HybridCritic (`R1–R7`):** Vòng lặp tác tử tự trị không phụ thuộc framework cồng kềnh: `Aggregator -> InsightEngine -> ActionPlanner <-> HybridCritic (R1–R7) -> Auto-Repair -> Human Approval Gate`.
5. **Production-Ready & Offline Cache Mode:** Hỗ trợ song song PostgreSQL 16 và SQLite, chế độ `DEMO_CACHE_MODE=true` dựa trên kho cache SHA-256 (vận hành tức thì không tốn chi phí token) và hồ bơi fallback đa mô hình.

---

## 🚀 Hướng Dẫn Khởi Chạy Nhanh 1-Click (`Quick Start`)

### Cách 1: Khởi chạy bằng Docker Compose (Khuyên dùng khi triển khai Backend)
```bash
# 1. Sao chép file cấu hình môi trường
cp .env.example .env

# 2. Khởi chạy 2 dịch vụ Backend (PostgreSQL 16 + FastAPI Backend)
docker compose up --build -d
```
- **Tài liệu Swagger UI tương tác (15 Endpoints):** `http://localhost:8000/docs`
- **OpenAPI Schema (JSON):** `http://localhost:8000/openapi.json`
- **Kiểm tra trạng thái sức khỏe:** `http://localhost:8000/api/v1/health`

### Cách 2: Khởi chạy trên Môi trường Cục bộ (`Local Python Virtualenv`)
```powershell
# 1. Kích hoạt môi trường ảo và cài đặt thư viện
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2. Nạp dữ liệu mẫu khởi đầu
python scripts/seed_demo.py

# 3. Khởi chạy FastAPI Backend Server (cổng 8000)
python -m uvicorn ecomreview.api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🛡️ Xác Thực & Cấu Hình Bảo Mật

Backend hỗ trợ xác thực header qua:
- **`X-API-Key`:** Khóa API chứng thực quyền truy cập (cấu hình tại biến môi trường `ECOMREVIEW_API_KEY`). Khi để trống, API hoạt động ở chế độ mở cho môi trường dev.
- **`X-Reviewer`:** Định danh người duyệt (ví dụ: `chu_shop_aomua`, `lead_marketer`) để lưu vết kiểm toán (`audit log`) trong bảng `action_feedback`.
- **`ECOMREVIEW_CORS_ORIGINS`:** Cấu hình danh sách tên miền Frontend được phép gọi API (mặc định chấp nhận `*` trong dev mode).

---

## 📊 Bản Đồ 15 RESTful API Endpoints Cho Frontend Kết Nối

| STT | Phương thức | Đường dẫn API | Tác dụng & Cơ chế hoạt động |
| :---: | :---: | :--- | :--- |
| 1 | `GET` | `/api/v1/health` | Kiểm tra trạng thái hệ thống, kết nối DB và số lượng review hiện có. |
| 2 | `POST` | `/api/v1/reviews/upload` | Nạp lô đánh giá mới, tự động khử khuẩn PII, phân tích ABSA và lưu CSDL. |
| 3 | `POST` | `/api/v1/analyze/run` | Kích hoạt phân tích ABSA và sinh Insight (hỗ trợ `async_mode` chạy nền). |
| 4 | `GET` | `/api/v1/jobs/{job_id}` | Tra cứu tiến độ và kết quả của tác vụ chạy ngầm (polling cho progress bar). |
| 5 | `GET` | `/api/v1/stats/overview` | Lấy toàn bộ KPI, tỷ lệ % 8 khía cạnh kèm khoảng tin cậy Wilson 95% CI. |
| 6 | `GET` | `/api/v1/insights` | Lấy danh sách 5 loại Insight đã qua kiểm thực số liệu (`verify_numbers`). |
| 7 | `POST` | `/api/v1/actions/generate` | Kích hoạt State-Graph (`Planner <-> Critic R1-R7`) để sinh đề xuất hành động. |
| 8 | `GET` | `/api/v1/actions` | Lấy danh sách kế hoạch Marketing & Vận hành kèm điểm ưu tiên `priority_score`. |
| 9 | `POST` | `/api/v1/actions/{id}/decision` | Người dùng duyệt (`APPROVED`, `EDITED`, `REJECTED`) kèm vết kiểm toán người duyệt. |
| 10 | `GET` | `/api/v1/reviews` | Tra cứu danh sách đánh giá kèm phân trang (`limit`, `offset`), lọc theo khía cạnh/sàn. |
| 11 | `GET` | `/api/v1/trends` | Lấy chuỗi dữ liệu xu hướng theo tháng (`month`) hoặc tuần (`week`) để vẽ biểu đồ. |
| 12 | `GET` | `/api/v1/alerts` | Lấy danh sách cảnh báo sớm khi tỷ lệ phàn nàn tăng đột biến (z-test một phía). |
| 13 | `POST` | `/api/v1/reviews/{id}/reply-draft` | Trợ lý CSKH tự động soạn câu trả lời an toàn tuân thủ 6 Guardrails G1–G6. |
| 14 | `GET` | `/api/v1/actions/{id}/impact` | Đo lường hiệu quả trước/sau can thiệp của hành động đã duyệt (`improved`/`worsened`). |
| 15 | `GET` | `/api/v1/reports/export` | Xuất Báo cáo Điều hành Excel 6 sheet (`.xlsx`) hoặc báo cáo HTML in ra PDF. |

---

## 🧪 Kiểm Thử & Kiểm Tra Chất Lượng Code

```powershell
# Chạy bộ kiểm thử tự động toàn diện
pytest -v

# Kiểm tra định dạng và chuẩn mực mã nguồn (Ruff PEP 8)
python -m ruff check .
python -m ruff format . --check
```

---

## 📂 Lưu Trữ Tài Liệu & Nghiên Cứu
Toàn bộ các tài liệu nghiên cứu học thuật, baseline thử nghiệm (B2, B3, P0) và báo cáo khoa học được lưu trữ tại thư mục [`Abount_System/`](Abount_System/).

<!-- CreBy: MenBoyBMN -->
