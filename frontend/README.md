# 🌧️ EcomReview AI — Modern SaaS Executive Frontend

Giao diện điều hành trực quan (SPA) dành cho chủ shop và đội ngũ Marketing SME, được xây dựng bằng **React 18 + Vite + Tailwind CSS + Recharts + Lucide Icons**, kết nối trực tiếp với **15 RESTful API Endpoints** của FastAPI Backend.

---

## ✨ 4 Phân Khu Chức Năng Cốt Lõi

1. **Tab 1 — Tổng Quan KPI & Biểu Đồ ABSA (`/api/v1/stats/overview`, `/api/v1/trends`):**
   - 4 Thẻ Bento KPI: Tổng đánh giá (tách sàn Shopee & TikTok Shop), Điểm sao trung bình, Tỷ lệ phàn nàn kèm khoảng tin cậy bất đối xứng **Wilson 95% CI**, và Phàn nàn ẩn trong đánh giá 4–5 sao.
   - Biểu đồ ngang phân tích cảm xúc **8 Khía cạnh Áo mưa** kèm Tooltip hiển thị khoảng tin cậy 95%.
   - Biểu đồ miền (Area Chart) theo dõi diễn biến xu hướng cảm xúc theo **Tháng / Tuần** và lọc theo từng khía cạnh.
   - Bảng đối sánh liên sàn **Shopee vs TikTok Shop** sử dụng kiểm định thống kê $z$-test 2 tỷ lệ ($p < 0.05$).

2. **Tab 2 — 5 Nhóm Insights & Cảnh Báo Sớm (`/api/v1/insights`, `/api/v1/alerts`, `/api/v1/analyze/run`, `/api/v1/jobs/{id}`):**
   - Hệ thống cảnh báo sớm phát hiện đột biến phàn nàn (One-sided $z$-test).
   - Bộ lọc 5 nhóm Insight (`TOP_PAIN`, `STRENGTH`, `HIDDEN_COMPLAINT`, `PLATFORM_GAP`, `EMERGING_ISSUE`) đã qua kiểm thực 100% số liệu (`verify_numbers_in_statement`).
   - Hỗ trợ chạy phân tích đồng bộ (Sync) hoặc tác vụ chạy nền (Async Job Polling) và xem trực tiếp bằng chứng đánh giá gốc (`EvidenceModal`).

3. **Tab 3 — Kế Hoạch Hành Động Marketing & Cổng Phê Duyệt (`/api/v1/actions/generate`, `/api/v1/actions`, `/api/v1/actions/{id}/decision`, `/api/v1/actions/{id}/impact`):**
   - Kích hoạt **P1 State-Graph** (`Aggregator -> InsightEngine -> ActionPlanner ⇄ HybridCritic R1–R7 -> Auto-Repair -> Human Approval Gate`) kèm hiển thị thông số Trace.
   - Phân tách rõ **Hành động Marketing (`is_marketing = True`)** và **Vận hành / Sản phẩm (`is_marketing = False`)**.
   - Cổng phê duyệt trực tiếp (**Duyệt `APPROVED`**, **Sửa & Duyệt `EDITED`** tự tính khoảng cách Levenshtein, **Từ chối `REJECTED`**) kèm định danh `X-Reviewer`.
   - Công cụ đo lường hiệu quả trước/sau can thiệp (**Pre/Post Intervention Impact**).

4. **Tab 4 — Kho Review ABSA & Trợ Lý CSKH Tự Động (`/api/v1/reviews`, `/api/v1/reviews/{id}/reply-draft`, `/api/v1/reviews/upload`, `/api/v1/reports/export`):**
   - Bộ lọc đa chiều theo Sàn, 8 Khía cạnh, Sắc thái cảm xúc kèm phân trang.
   - Trợ lý CSKH tự động soạn câu trả lời lịch sự (chế độ Chuẩn Template hoặc AI LLM) đạt **6/6 Guardrails an toàn (`G1–G6`)**.
   - Cửa sổ nạp đánh giá mới (`UploadModal`) và nút xuất báo cáo **Excel 6 Sheet (`.xlsx`)** / **HTML**.

---

## 🚀 Hướng Dẫn Khởi Chạy Nhanh

### Bước 1: Khởi chạy FastAPI Backend (Cổng 8000)
Tại thư mục gốc của dự án `EcomReview AI`:
```powershell
.\.venv\Scripts\python -m uvicorn ecomreview.api.main:app --host 127.0.0.1 --port 8000 --reload
```

### Bước 2: Cài đặt & Khởi chạy Frontend (Cổng 5173)
Mở một cửa sổ Terminal thứ hai tại thư mục `frontend`:
```powershell
cd frontend
npm install
npm run dev
```
Sau đó mở trình duyệt tại địa chỉ: **`http://localhost:5173`**

<!-- CreBy: MenBoyBMN -->

