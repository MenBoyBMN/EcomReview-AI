---
name: absa-evaluator
description: Kiểm định chất lượng phân tích ABSA tiếng Việt, kiểm thử hồi quy (Regression Testing) và giám sát SLA cho các động cơ AI trong môi trường Production.
---

# ABSA Production Quality & Regression Evaluator Skill

Kỹ năng này hướng dẫn quy trình kiểm định chất lượng phân loại cảm xúc theo khía cạnh (ABSA), kiểm thử chống thoái lui (Regression Gate) khi cập nhật Prompt/Lexicon và đánh giá độ ổn định của các động cơ AI (`Gemini Cloud`, `Ollama Local`, `B1 Rule Fallback`) trong **EcomReview AI**.

## 1. Tiêu Chí Đánh Giá Độ Chính Xác Trong Production
- **Precision, Recall, F1 theo từng Khía Cạnh (8 Aspects):**
  - True Positive ($TP$): Nhận diện đúng mã khía cạnh (`WATERPROOF`, `FIT_SIZE`, ...) và đúng cực cảm xúc (`POSITIVE`, `NEGATIVE`, `NEUTRAL`).
  - False Positive ($FP$): Gán nhầm khía cạnh không được nhắc tới hoặc sai cực cảm xúc.
  - False Negative ($FN$): Bỏ sót khía cạnh khách hàng có phản ánh (đặc biệt nguy hiểm nếu bỏ sót phàn nàn `NEGATIVE`).
- **Macro-F1 & Khoảng Tin Cậy Bootstrap 95%:**
  - Tính trung bình cộng F1 trên 8 khía cạnh kèm khoảng tin cậy Bootstrap ($B = 1.000$, `seed = 42`) trên bộ Golden Regression Set để đảm bảo tính ổn định trước khi phát hành.

## 2. Kiểm Định Chống Thoái Lui & SLA Vận Hành (Production SLA Gate)
Khi chỉnh sửa `prompts/analyzer_v2_frozen.md`, `knowledge/vn_social_lexicon.yaml` hoặc `src/ecomreview/normalize.py`:
1. **Tuân thủ Schema 100%:** Toàn bộ phản hồi phải khớp tuyệt đối với Pydantic model `ReviewAnalysis` (không văng lỗi `ValidationError` chưa được xử lý).
2. **Kiểm thử hồi quy tự động:** Chạy bộ test `tests/test_regression.py`, `tests/test_a1_gemini.py` và `tests/test_analyzer_factory.py`.
3. **Độ trễ & Khả năng chịu lỗi:** Đảm bảo cơ chế cache SHA-256 (`data/cache/`) và fallback sang `B1RuleAnalyzer` hoạt động tức thì khi mất kết nối tới dịch vụ LLM.

<!-- CreBy: MenBoyBMN -->
