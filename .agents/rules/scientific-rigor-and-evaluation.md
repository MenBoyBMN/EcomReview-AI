# Quy Chuẩn Độ Tin Cậy Thống Kê, Đánh Giá Chất Lượng AI & Giám Sát Vận Hành (Production Reliability & Quality Assurance)

Trong một sản phẩm AI ứng dụng thực tế cho doanh nghiệp như **EcomReview AI**, các quyết định nhập hàng, sửa lỗi sản xuất hay điều chỉnh chiến dịch Marketing đều ảnh hưởng trực tiếp đến doanh thu và chi phí của cửa hàng. Do đó, hệ thống bắt buộc áp dụng các chuẩn mực thống kê xác thực và kiểm định chất lượng nghiêm ngặt trong môi trường Production.

---

## 1. Thống Kê Xác Thực Trong Vận Hành Thực Tế (Production Statistical Rigor)

### 1.1. Khoảng Tin Cậy Bất Đối Xứng Wilson 95% CI (`tools_aggregator.py`)
- Khi số lượng đánh giá của một sản phẩm mới hoặc trong một tuần còn ít (ví dụ: $n < 30$), tỷ lệ phần trăm đơn thuần ($p = k/n$) rất dễ gây hiểu lầm cho chủ shop.
- Hệ thống bắt buộc tính toán và trả về **Khoảng tin cậy Wilson 95% CI** (`neg_ci_low`, `neg_ci_high`) cho tỷ lệ phàn nàn của từng khía cạnh trong `/api/v1/stats/overview`.
- Mọi xếp hạng mức độ nghiêm trọng của vấn đề (`CRITICAL_ISSUE`) ưu tiên dựa trên cận dưới khoảng tin cậy (`neg_ci_low`) kết hợp tổng lượng mẫu để tránh báo động giả khi cỡ mẫu quá nhỏ.

### 1.2. Phát Hiện Cảnh Báo Sớm Bằng Kiểm Định Z-Test (`insight_engine.py`)
- Hệ thống giám sát biến động tỷ lệ phàn nàn giữa kỳ hiện tại ($p_{\text{curr}}, n_{\text{curr}}$) và kỳ liền trước ($p_{\text{prev}}, n_{\text{prev}}$) thông qua **Kiểm định Z một phía cho hai tỷ lệ (One-sided Two-proportion Z-test)**.
- Chỉ kích hoạt cảnh báo nóng (`/api/v1/alerts`) khi mức tăng tỷ lệ tiêu cực đạt ngưỡng ý nghĩa thống kê ($z \ge 1.645$, tương ứng $p\text{-value} \le 0.05$) hoặc vượt ngưỡng an toàn trong Playbook, giúp bộ phận vận hành phát hiện ngay các lô hàng bị lỗi gia công mới phát sinh.

### 1.3. Kiểm Thực Số Học Tự Động (`verify_numbers_in_statement`)
- Trước khi bất kỳ nhận định (`Insight`) hoặc lý do đề xuất (`ActionProposal.why_rationale`) nào được lưu trữ và hiển thị lên Dashboard, hàm `verify_numbers_in_statement()` sẽ trích xuất toàn bộ các con số trong câu và đối chiếu với tập số liệu gốc từ SQL Aggregator (sai số cho phép $\le 0.15$).
- Nếu phát hiện con số không có căn cứ, hệ thống tự động chặn hoặc kích hoạt cơ chế `Auto-Repair` trong `HybridCritic` để thay thế bằng số liệu chuẩn xác từ CSDL.

---

## 2. Kiểm Định Chất Lượng Pipeline AI & Chống Thoái Lui (AI Quality & Regression Gate)

Trước khi thay đổi System Prompt (`prompts/`), nâng cấp phiên bản mô hình LLM hoặc cập nhật từ điển chuẩn hóa (`knowledge/vn_social_lexicon.yaml`), bắt buộc thực hiện kiểm định chất lượng:

1. **Độ Đo Chất Lượng Phân Tích Khía Cạnh (ABSA Quality Metrics):**
   - Đánh giá đồng thời việc nhận diện đúng khía cạnh (8 khía cạnh chuẩn) và đúng sắc thái cảm xúc (`POSITIVE`, `NEGATIVE`, `NEUTRAL`).
   - Sử dụng độ đo **Macro-F1** kèm **Khoảng tin cậy Bootstrap 95%** ($B = 1.000$, `seed = 42`) trên bộ dữ liệu kiểm chuẩn (Golden Regression Set) để đảm bảo bản cập nhật mới không làm suy giảm độ chính xác trên các trường hợp teencode hoặc câu ghép phức tạp.

2. **Kiểm Thử Khả Năng Chịu Lỗi Đa Động Cơ (Multi-Engine Resilience Testing):**
   - Đảm bảo hệ thống hoạt động thông suốt ở cả 3 chế độ trong `UnifiedLLMClient`:
     - Chế độ Cloud (`EngineMode.GEMINI_CLOUD`).
     - Chế độ Local AI (`EngineMode.OLLAMA_LOCAL` với cơ chế tự sửa JSON `Self-Healing`).
     - Chế độ Dự phòng xác định (`B1RuleAnalyzer` khi mất mạng hoặc không có API Key).

---

## 3. Đo Lường Hiệu Quả Kinh Doanh Khép Kín (Closed-Loop Impact Evaluation)

Một sản phẩm Production thực thụ không chỉ dừng ở việc "đưa ra lời khuyên", mà phải đo lường được kết quả sau khi doanh nghiệp thực thi lời khuyên đó:
- Thông qua endpoint `GET /api/v1/actions/{id}/impact`, hệ thống tự động phân tách dữ liệu đánh giá thành 2 giai đoạn dựa trên thời điểm phê duyệt (`decided_at` / `cutoff_date`):
  - **Giai đoạn Trước can thiệp (`before_window`):** Tỷ lệ phàn nàn và điểm sao trung bình của khía cạnh mục tiêu trước khi áp dụng hành động.
  - **Giai đoạn Sau can thiệp (`after_window`):** Tỷ lệ phàn nàn và điểm sao trung bình sau khi hành động được triển khai.
- Hệ thống tự động tính toán độ lệch `delta_negative_rate` (điểm phần trăm) và phân loại trạng thái thực tế:
  - `improved`: Tỷ lệ phàn nàn giảm rõ rệt ($\Delta \le -2.0\%$).
  - `worsened`: Tỷ lệ phàn nàn tiếp tục tăng ($\Delta \ge +2.0\%$), cần can thiệp sâu hơn về sản xuất/vận hành.
  - `unchanged` / `insufficient_data`: Chưa đủ cỡ mẫu đánh giá mới hoặc biến động chưa đáng kể.

<!-- CreBy: MenBoyBMN -->
