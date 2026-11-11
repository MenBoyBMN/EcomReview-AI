# Tài Liệu Đặc Tả RESTful API — EcomReview AI (`OpenAPI 3.1 Reference`)

Dịch vụ Backend **FastAPI (`src/ecomreview/api/main.py`)** cung cấp **15 RESTful Endpoints** tại tiền tố `/api/v1` (mặc định lắng nghe trên cổng `http://localhost:8000`, tài liệu tương tác Swagger UI tại `http://localhost:8000/docs` và đặc tả máy đọc tại `docs/openapi.json`).

Hệ thống bảo vệ qua header xác thực `X-API-Key` (mặc định chấp nhận key môi trường `ECOMREVIEW_API_KEY` hoặc `demo-key-12345`) và định danh người duyệt qua `X-Reviewer` (ví dụ: `chu_shop_aomua`).

---

## 1. Bảng Tổng Hợp 15 RESTful Endpoints

| STT | Phương Thức | Đường Dẫn (`Endpoint Path`) | Chức Năng Nghiệp Vụ | Mã Phản Hồi |
| :-: | :-: | :--- | :--- | :-: |
| 1 | `GET` | `/api/v1/health` | Kiểm tra trạng thái hoạt động của API, backend CSDL (`sqlite`/`postgres`) và chế độ `DEMO_CACHE_MODE`. | `200 OK` |
| 2 | `POST` | `/api/v1/reviews/upload` | Tải lên danh sách đánh giá khách hàng (JSON), tự động ẩn danh PII (`scrub_pii`) và lưu vào CSDL. | `200 OK` |
| 3 | `POST` | `/api/v1/analyze/run` | Kích hoạt bộ phân tích ABSA (`A1 Gemini` / `B1` / `B2` / `B3`), hỗ trợ `async_mode=true` (Background Job). | `200 / 202` |
| 4 | `GET` | `/api/v1/jobs/{job_id}` | Truy vấn trạng thái tiến trình xử lý trong bảng kiểm toán `system_jobs_audit`. | `200 / 404` |
| 5 | `GET` | `/api/v1/stats/overview` | Lấy thống kê tổng quan, tỷ lệ tiêu cực kèm khoảng tin cậy bất đối xứng **Wilson 95% CI** theo 8 khía cạnh. | `200 OK` |
| 6 | `GET` | `/api/v1/insights` | Lấy danh sách các nhận định kinh doanh (`TOP_PAIN`, `STRENGTH`, `HIDDEN_COMPLAINT`, `PLATFORM_GAP`, `EMERGING_ISSUE`). | `200 OK` |
| 7 | `POST` | `/api/v1/actions/generate` | Chạy đồ thị trạng thái `EcomReviewGraphRunner` (`Insight -> Planner <-> HybridCritic R1-R7 -> Auto-Repair`). | `200 OK` |
| 8 | `GET` | `/api/v1/actions` | Truy vấn danh sách đề xuất hành động (hỗ trợ lọc theo `scenario_tag` và `is_marketing`). | `200 OK` |
| 9 | `POST` | `/api/v1/actions/{action_id}/decision` | Ghi nhận quyết định phê duyệt (`APPROVED`, `EDITED`, `REJECTED`), lưu `decided_by` và `edit_distance_chars`. | `200 / 400` |
| 10 | `GET` | `/api/v1/reviews` | Tra cứu danh sách đánh giá gốc và bằng chứng trích xuất (truy vấn tối ưu giải quyết N+1 query). | `200 OK` |
| 11 | `GET` | `/api/v1/trends` | Lấy chuỗi thời gian xu hướng theo tháng/tuần/ngày và tỷ lệ phàn nàn theo khía cạnh. | `200 OK` |
| 12 | `GET` | `/api/v1/alerts` | Cảnh báo sớm (`HIGH`/`MEDIUM`/`WATCH`) dựa trên kiểm định thống kê **two-proportion z-test** ($p < 0.05$). | `200 OK` |
| 13 | `POST` | `/api/v1/reviews/{review_id}/reply-draft` | Trợ lý soạn thảo phản hồi CSKH tự động tuân thủ 6 Guardrails (`G1–G6`) bảo vệ chính sách sàn. | `200 / 404` |
| 14 | `GET` | `/api/v1/actions/{action_id}/impact` | Đo lường hiệu quả trước/sau khi can thiệp hành động marketing / sản phẩm (`Intervention Impact`). | `200 / 404` |
| 15 | `GET` | `/api/v1/reports/export` | Xuất Báo cáo Điều hành toàn diện dưới định dạng **Excel 6 sheet (`.xlsx`)** hoặc **HTML in PDF**. | `200 OK` |

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
  "reason_category": "TIMELINE_ADJUSTMENT",
  "decided_by": "chu_shop_aomua"
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

### 2.6. `GET /api/v1/trends?scenario_tag=real_shop&interval=month`
**Response (`200 OK`):**
```json
{
  "scenario_tag": "real_shop",
  "interval": "month",
  "aspect": null,
  "total_periods": 6,
  "periods": [
    {
      "period": "2026-08",
      "total_reviews": 25,
      "avg_rating": 4.12,
      "aspect_neg_counts": {"WATERPROOF": 3, "MATERIAL_DURABILITY": 2}
    }
  ]
}
```

### 2.7. `GET /api/v1/alerts?scenario_tag=real_shop`
**Response (`200 OK`):**
```json
{
  "scenario_tag": "real_shop",
  "alerts_count": 1,
  "alerts": [
    {
      "aspect": "MATERIAL_DURABILITY",
      "severity": "HIGH",
      "z_score": 2.7104,
      "p_value": 0.0034,
      "baseline_neg_rate": 0.12,
      "recent_neg_rate": 0.35,
      "message": "Tỷ lệ tiêu cực tăng vọt có ý nghĩa thống kê (p=0.0034 < 0.05)"
    }
  ]
}
```

### 2.8. `POST /api/v1/reviews/{review_id}/reply-draft`
**Request Body:**
```json
{
  "shop_name": "Shop Áo Mưa Thời Trang",
  "support_hotline": "1900-xxxx",
  "use_llm": false
}
```
**Response (`200 OK`):**
```json
{
  "review_id": "r_neg_01",
  "reply_text": "Dạ Shop Áo Mưa Thời Trang chân thành xin lỗi bạn về trải nghiệm chưa tốt...",
  "method": "template_rule",
  "guardrails_check": {
    "passed": true,
    "violations": []
  }
}
```

### 2.9. `GET /api/v1/actions/{action_id}/impact`
**Response (`200 OK`):**
```json
{
  "action_id": 1,
  "title": "Gia cố băng keo ép nhiệt",
  "aspect": "WATERPROOF",
  "status": "sufficient_data",
  "pre_period": {"total_reviews": 30, "neg_count": 10, "neg_rate_pct": 33.3},
  "post_period": {"total_reviews": 25, "neg_count": 2, "neg_rate_pct": 8.0},
  "improvement_pct_points": 25.3,
  "is_significant": true,
  "p_value": 0.018
}
```

### 2.10. `GET /api/v1/reports/export?scenario_tag=real_shop&format=xlsx`
**Response (`200 OK`):**
File nhị phân `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` chứa 6 sheet nghiệp vụ: *1. Tổng Quan*, *2. Khía Cạnh & Wilson CI*, *3. Cảnh Báo Sớm*, *4. Đề Xuất Hành Động*, *5. So Sánh Nền Tảng*, *6. Vết Phê Duyệt*.

<!-- CreBy: MenBoyBMN -->

