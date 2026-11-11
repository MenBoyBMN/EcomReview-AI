# Tài Liệu Đặc Tả RESTful API — EcomReview AI (`OpenAPI 3.1 Reference`)

Dịch vụ Backend **FastAPI (`src/ecomreview/api/main.py`)** cung cấp **10 RESTful Endpoints** tại tiền tố `/api/v1` (mặc định lắng nghe trên cổng `http://localhost:8000`, tài liệu tương tác Swagger UI tại `http://localhost:8000/docs` và đặc tả máy đọc tại `docs/openapi.json`).

---

## 1. Bảng Tổng Hợp 10 RESTful Endpoints

| STT | Phương Thức | Đường Dẫn (`Endpoint Path`) | Chức Năng Nghiệp Vụ | Mã Phản Hồi |
| :-: | :-: | :--- | :--- | :-: |
| 1 | `GET` | `/api/v1/health` | Kiểm tra trạng thái hoạt động của API, kết nối CSDL và chế độ `DEMO_CACHE_MODE`. | `200 OK` |
| 2 | `POST` | `/api/v1/reviews/upload` | Tải lên danh sách đánh giá khách hàng (JSON), tự động ẩn danh PII (`scrub_pii`) và lưu vào CSDL. | `200 OK` |
| 3 | `POST` | `/api/v1/analyze/run` | Kích hoạt bộ phân tích ABSA (`B1 / B2 / B3 / A1 Gemini`) trên kịch bản `scenario_tag`. | `200 OK` |
| 4 | `GET` | `/api/v1/jobs/{job_id}` | Truy vấn trạng thái tiến trình xử lý trong bảng kiểm toán `system_jobs_audit`. | `200 / 404` |
| 5 | `GET` | `/api/v1/stats/overview` | Lấy thống kê tổng quan, tỷ lệ tiêu cực kèm khoảng tin cậy bất đối xứng **Wilson 95% CI** theo 8 khía cạnh. | `200 OK` |
| 6 | `GET` | `/api/v1/insights` | Lấy danh sách các nhận định kinh doanh (`TOP_PAIN`, `STRENGTH`, `HIDDEN_COMPLAINT`, `PLATFORM_GAP`, `EMERGING_ISSUE`). | `200 OK` |
| 7 | `POST` | `/api/v1/actions/generate` | Chạy đồ thị trạng thái `EcomReviewGraphRunner` (`Insight -> Planner <-> HybridCritic R1-R7 -> Auto-Repair`). | `200 OK` |
| 8 | `GET` | `/api/v1/actions` | Truy vấn danh sách đề xuất hành động (hỗ trợ lọc theo `scenario_tag` và `is_marketing`). | `200 OK` |
| 9 | `POST` | `/api/v1/actions/{action_id}/decision` | Ghi nhận quyết định phê duyệt của chủ shop (`APPROVED`, `EDITED`, `REJECTED`) và tính `edit_distance_chars`. | `200 / 400` |
| 10 | `GET` | `/api/v1/reviews` | Tra cứu danh sách đánh giá gốc và bằng chứng trích xuất theo `scenario_tag`, `aspect`, `polarity`. | `200 OK` |

---

## 2. Chi Tiết Request / Response Mẫu Cho Các Endpoint Trọng Tâm

### 2.1. `GET /api/v1/health`
**Response (`200 OK`):**
```json
{
  "status": "healthy",
  "database": "connected",
  "total_reviews_in_db": 554,
  "demo_cache_mode": true
}
```

### 2.2. `POST /api/v1/reviews/upload`
**Request Body:**
```json
{
  "scenario_tag": "real_shop",
  "reviews": [
    {
      "review_id": "shp_9001",
      "platform": "shopee",
      "shop": "shop_aomua_vn",
      "product": "ao_mua_bo_da_ca",
      "rating": 2,
      "text": "Đi mưa lớn nước ngấm qua đường may đáy quần, gọi mình số 0912345678 nhé"
    }
  ]
}
```
**Response (`200 OK`):** Tự động che giấu số điện thoại thành `[PHONE]` và lưu vào bảng `reviews`.

### 2.3. `GET /api/v1/stats/overview?scenario_tag=real_shop&min_n=5`
**Response (`200 OK`):**
```json
{
  "scenario_tag": "real_shop",
  "total_reviews": 150,
  "avg_rating": 4.28,
  "positive_reviews": 102,
  "negative_reviews": 38,
  "negative_rate_pct": 25.3,
  "negative_ci_95": [19.0, 32.8],
  "platform_counts": {
    "shopee": 45,
    "tiktok": 105
  },
  "aspect_stats": [
    {
      "aspect": "WATERPROOF",
      "total": 18,
      "neg_count": 9,
      "pos_count": 9,
      "neg_pct": 50.0,
      "ci_low": 29.0,
      "ci_high": 71.0
    }
  ],
  "hidden_complaints": {
    "hidden_count": 23,
    "high_rating_total": 135,
    "hidden_pct": 17.0
  }
}
```

### 2.4. `POST /api/v1/actions/generate`
**Request Body:**
```json
{
  "scenario_tag": "S1",
  "min_n": 5,
  "max_actions": 4
}
```
**Response (`200 OK`):**
```json
{
  "scenario_tag": "S1",
  "insights_count": 2,
  "actions_count": 3,
  "retries_used": 3,
  "auto_repaired": true,
  "final_critic_passed": true,
  "final_critic_score": 5.0,
  "actions": [
    {
      "action_id": "act_001",
      "action_type": "PRODUCT_FIX",
      "is_marketing": false,
      "title": "Gia cố băng keo ép nhiệt đường may đáy quần và nẹp khóa kéo",
      "priority_score": 4.04,
      "insight_ids": [1],
      "evidence_review_ids": ["s1_rev_010", "s1_rev_011", "s1_rev_012", "s1_rev_013"]
    }
  ]
}
```

### 2.5. `POST /api/v1/actions/{action_id}/decision`
**Request Body:**
```json
{
  "decision": "EDITED",
  "edited_content": "Kiểm tra lô hàng tồn kho và yêu cầu xưởng tăng nhiệt độ ép seam tape trong 24h.",
  "note": "Rút ngắn thời hạn kiểm tra xuống 24h",
  "reason_category": "TIMELINE_ADJUSTMENT"
}
```
**Response (`200 OK`):**
```json
{
  "feedback_id": 12,
  "action_id": 1,
  "decision": "EDITED",
  "edit_distance_chars": 42
}
```

<!-- CreBy: MenBoyBMN -->

