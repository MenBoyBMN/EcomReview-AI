# Chương 3 (Phần 2): Thiết Kế Cơ Sở Dữ Liệu Quan Hệ, Bộ Tổng Hợp Thống Kê Wilson 95% CI Và Động Cơ Khai Phá Nhận Định (Insight Engine)

## 3.4. Kiến Trúc Cơ Sở Dữ Liệu Quan Hệ (Database Schema & Read-Only Isolation)

Để đảm bảo nguyên tắc kiến trúc bất biến số 1 (**Zero-Hallucination Metrics via SQL/Python Aggregator**) và nguyên tắc số 3 (**Defense-in-Depth Security**), toàn bộ dữ liệu đánh giá khách hàng, kết quả trích xuất ABSA, nhận định kinh doanh và kế hoạch hành động được lưu trữ trong cơ sở dữ liệu quan hệ chuẩn hóa gồm 6 bảng cốt lõi (`docker/db/init.sql` và `src/ecomreview/db/database.py`):

1. **`reviews`**: Lưu trữ đánh giá gốc của khách hàng cùng siêu dữ liệu (`review_id`, `platform` $\in \{\text{shopee}, \text{tiktok}\}$, `product_id`, `rating` $1..5$, `review_text`, `clean_text`, `has_teencode`, `is_no_diacritics`, `has_emoji`, `is_spam`, `is_injection_suspect`, `overall_sentiment`, `overall_confidence`, `review_date`).
2. **`opinions`**: Quan hệ $1\text{-}N$ với `reviews`, lưu từng cặp `(aspect, sentiment)` cùng `evidence_quote` nguyên văn, `quote_verified` (boolean xác thực trích dẫn có nằm trong review gốc), `severity` và `confidence`.
3. **`insights`**: Lưu các nhận định kinh doanh có căn cứ thống kê (`insight_id`, `insight_type`, `aspect`, `platform`, `statement`, `support_count`, `rate_pct`, `ci_low_pct`, `ci_high_pct`, `evidence_review_ids` dạng JSON array, `severity_score`).
4. **`actions`**: Lưu các đề xuất hành động của Agent (`action_id`, `action_type`, `is_marketing`, `title`, `what_to_do`, `why_rationale`, `how_and_when`, `success_metric`, `effort`, `impact`, `priority_score`, `insight_ids`, `evidence_review_ids`, `critic_passed`, `critic_score`, `retry_count`, `status`).
5. **`action_feedback`**: Lưu vết quyết định của chủ shop trong cơ chế *Human-in-the-Loop Approval Gate* (`feedback_id`, `action_id`, `decision` $\in \{\text{APPROVED}, \text{EDITED}, \text{REJECTED}\}$, `edited_text`, `edit_distance_chars`, `reviewer_note`).
6. **`system_jobs_audit`**: Ghi nhật ký kiểm toán toàn bộ các tiến trình chạy bất đồng bộ (`job_id`, `job_type`, `status`, `records_processed`, `duration_ms`, `details_json`).

**Cơ chế cô lập quyền đọc (Read-Only Connection Isolation):** Mọi truy vấn từ tầng Agent (`tools_aggregator.py`, `insight_engine.py`) đều kết nối qua `DatabaseManager.get_connection(read_only=True)`, kích hoạt chế độ `PRAGMA query_only = ON` (trên SQLite) hoặc `SET TRANSACTION READ ONLY` (trên PostgreSQL 16). Nhờ đó, ngay cả trong kịch bản giả định câu lệnh SQL bị thao túng, tiến trình phân tích của Agent hoàn toàn không thể ghi đè hay xóa dữ liệu nghiệp vụ.

---

## 3.5. Bộ Tổng Hợp Thống Kê Xác Định & Khoảng Tin Cậy Bất Đối Xứng Wilson 95% CI

Một sai lầm phổ biến của các hệ thống phân tích đánh giá thương mại điện tử dựa trên LLM là để mô hình ngôn ngữ tự ước lượng tỷ lệ phần trăm từ một vài mẫu trong ngữ cảnh, hoặc sử dụng công thức khoảng tin cậy chuẩn đối xứng (Wald interval) $\hat{p} \pm z \sqrt{\hat{p}(1-\hat{p})/n}$. Khi cỡ mẫu $n$ nhỏ (ví dụ một khía cạnh mới phát sinh chỉ có $n=8$ lượt nhắc) hoặc tỷ lệ $\hat{p}$ tiến gần $0\%$ hay $100\%$, khoảng Wald bị suy biến và có thể vượt quá đoạn $[0, 1]$.

Hệ thống **EcomReview AI** giải quyết triệt để vấn đề này trong module `src/ecomreview/agent/tools_aggregator.py` bằng công thức **Khoảng tin cậy Wilson 95%** (Wilson Score Interval, $z = 1.96$):

$$\text{CI}_{\text{Wilson}} = \frac{\hat{p} + \frac{z^2}{2n} \pm z \sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$

Bảng 3.2 minh họa sự khác biệt của khoảng tin cậy Wilson 95% trên dữ liệu thực tế của Shop Áo Mưa ($N = 165$ đánh giá):

| Khía cạnh (`aspect`) | Tổng lượt nhắc ($n$) | Lượt tiêu cực ($k$) | Tỷ lệ tiêu cực ($\hat{p}$) | Khoảng tin cậy Wilson 95% $[\text{CI}_{\text{low}}, \text{CI}_{\text{high}}]$ | Độ rộng bất đối xứng ($\Delta_-, \Delta_+$) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `WATERPROOF` | 81 | 44 | 54.3% | $[43.5\%, 64.7\%]$ | $-10.8\% / +10.4\%$ |
| `MATERIAL_DURABILITY` | 91 | 41 | 45.1% | $[35.2\%, 55.3\%]$ | $-9.9\% / +10.2\%$ |
| `FIT_SIZE` | 48 | 19 | 39.6% | $[27.0\%, 53.7\%]$ | $-12.6\% / +14.1\%$ |
| `PACKAGING_SHIPPING` | 53 | 17 | 32.1% | $[21.1\%, 45.5\%]$ | $-11.0\% / +13.4\%$ |
| `COMFORT_USABILITY` | 35 | 10 | 28.6% | $[16.3\%, 45.1\%]$ | $-12.3\% / +16.5\%$ |
| `CUSTOMER_SERVICE` | 15 | 6 | 40.0% | $[19.8\%, 64.3\%]$ | $-20.2\% / +24.3\%$ |

Các công cụ truy vấn xác định (Deterministic Tools) được cung cấp cho Insight Engine bao gồm:
- `get_aspect_sentiment_stats(db, platform)`: Trả về bảng thống kê đầy đủ $(n, k_{\text{pos}}, k_{\text{neg}}, k_{\text{neu}}, \hat{p}_{\text{neg}}, \text{CI}_{\text{low}}, \text{CI}_{\text{high}})$ cho từng khía cạnh.
- `get_platform_gap_stats(db, min_mentions=5)`: So sánh chênh lệch tỷ lệ tiêu cực $\Delta_{\text{platform}} = |\hat{p}_{\text{neg, Shopee}} - \hat{p}_{\text{neg, TikTok}}|$ giữa 2 sàn TMĐT.
- `get_hidden_complaints(db, min_rating=4)`: Phát hiện các đánh giá chấm **4–5 sao** nhưng bên trong văn bản lại chứa phàn nàn tiêu cực (`sentiment = NEGATIVE`) về sản phẩm/dịch vụ.

---

## 3.6. Thuật Toán Tuyển Chọn Bằng Chứng Đa Dạng (`select_representative_evidence`)

Để mỗi nhận định (`Insight`) và đề xuất hành động (`ActionProposal`) luôn đi kèm bằng chứng cụ thể mà không bị trùng lặp ngữ nghĩa (ví dụ 5 câu review cùng viết *"áo mưa mỏng quá"*), module `src/ecomreview/agent/evidence_selector.py` cài đặt thuật toán tham lam có ràng buộc đa dạng từ vựng (Greedy Lexical-Diversity Evidence Selection):

1. **Chấm điểm ứng viên:** Ưu tiên các review có `quote_verified = 1`, độ dài câu trích dẫn nằm trong vùng giàu thông tin ($15 \le |\text{quote}| \le 180$ ký tự), và độ tin cậy `confidence` cao.
2. **Lọc trùng lặp Jaccard ($J \le 0.70$):** Với mỗi ứng viên tiếp theo $c$, tính độ tương đồng Jaccard trên tập từ (word-level token set) so với mọi bằng chứng đã chọn $s \in S$:
   $$J(c, s) = \frac{|W(c) \cap W(s)|}{|W(c) \cup W(s)|}$$
   Nếu $\max_{s \in S} J(c, s) > 0.70$, ứng viên $c$ bị loại bỏ để nhường chỗ cho góc nhìn khác (ví dụ: câu 1 nói về *thấm nước ở đường may đáy quần*, câu 2 nói về *nước tạt qua cổ áo*, câu 3 nói về *keo ép nhiệt bong sau 2 lần mặc*).

---

## 3.7. Động Cơ Khai Phá 5 Loại Nhận Định Kinh Doanh (Insight Engine & Number Verification Guard)

Module `src/ecomreview/agent/insight_engine.py` kết hợp kết quả từ `tools_aggregator` và `evidence_selector` để tự động tổng hợp **5 nhóm nhận định kinh doanh cốt lõi**:
1. **`TOP_PAIN_POINT`**: Các khía cạnh có tỷ lệ phàn nàn tiêu cực cao nhất ($\hat{p}_{\text{neg}} \ge 25\%$), xếp hạng theo điểm nghiêm trọng $\text{Severity} = \hat{p}_{\text{neg}} \times \ln(1 + n)$.
2. **`TOP_STRENGTH`**: Điểm mạnh nổi bật của sản phẩm ($\hat{p}_{\text{pos}} \ge 55\%$) làm chất liệu cho nội dung quảng cáo (Content/Listing).
3. **`PLATFORM_GAP`**: Chênh lệch trải nghiệm khách hàng giữa Shopee và TikTok Shop ($\Delta_{\text{platform}} \ge 8\%$).
4. **`HIDDEN_COMPLAINT`**: Rủi ro tiềm ẩn từ nhóm khách hàng chấm 4–5 sao vì lịch sự hoặc vì giao hàng nhanh nhưng phàn nàn về chất lượng thực tế của áo mưa.
5. **`EMERGING_ISSUE`**: Các vấn đề ngoại lai nằm trong nhãn `GENERAL_OTHER` được gom cụm từ khóa tự động để cảnh báo sớm cho chủ shop.

**Chốt chặn xác thực số liệu (`verify_numbers_in_statement`):** Mọi câu phát biểu nhận định (`statement`) trước khi lưu vào bảng `insights` đều phải đi qua hàm kiểm tra biểu thức chính quy đối chiếu 100% các con số xuất hiện trong câu văn với tập số liệu gốc từ SQL (`total_mentions`, `neg_count`, `neg_rate_pct`, `ci_low_pct`, `ci_high_pct`). Nếu phát hiện bất kỳ con số nào lệch quá $\pm 0.15$ so với nguồn SQL, hệ thống lập tức bác bỏ và回退 (fallback) về mẫu câu xác định (`format_deterministic_insight`), đảm bảo tỷ lệ ảo giác số liệu bằng **0.0% tuyệt đối**.

<!-- CreBy: MenBoyBMN -->

