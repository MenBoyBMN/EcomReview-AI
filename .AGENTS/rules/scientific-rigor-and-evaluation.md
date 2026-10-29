# Quy Chuẩn Nghiên Cứu Khoa Học & Đánh Giá Thực Nghiệm (Scientific Rigor & Evaluation)

Tài liệu này quy định các tiêu chuẩn bắt buộc khi thực hiện nghiên cứu, thiết kế thực nghiệm và phân tích kết quả trong dự án **EcomReview AI**.

---

## 1. Ba Câu Hỏi Nghiên Cứu (Research Questions - RQ)
Mọi thí nghiệm và phân tích dữ liệu phải xoay quanh và trả lời dứt khoát 3 câu hỏi nghiên cứu sau:

1. **RQ1 (Hiệu năng ABSA tiếng Việt):**
   - Mô hình LLM Gemini Flash (Structured Output) đạt độ chính xác (Macro F1, Precision, Recall) so với 3 thế hệ Baselines như thế nào trên tập dữ liệu thương mại điện tử tiếng Việt?
   - Baselines so sánh:
     - **B1:** Rule-based / Lexicon-based.
     - **B2:** TF-IDF + Logistic Regression.
     - **B3:** ViSoBERT (`uitnlp/visobert`) fine-tuned.
     - **A1 (Đề xuất):** Gemini Flash có cấu trúc Pydantic.

2. **RQ2 (Khả năng chịu lỗi & Chuyển miền):**
   - Khi gặp ngôn ngữ mạng xã hội (teencode, viết tắt, tiếng lóng, emoji, đánh giá ẩn ý) hoặc chuyển từ tập công khai sang dữ liệu thực tế của Shop Áo Mưa, độ suy giảm hiệu năng ($\Delta F_1$) của các mô hình diễn ra như thế nào?
   - Thí nghiệm Ablation: Đo lường tác động của bước chuẩn hóa teencode (`normalize.py`).

3. **RQ3 (Tính Hữu Dụng & Căn Cứ Thực Tế Của AI Agent):**
   - Kế hoạch hành động marketing do State-Graph Agent đề xuất (P1: Planner ⇄ Hybrid Critic) vượt trội hơn phương pháp Baseline (P0: Single-Prompt LLM không qua Aggregator/Playbook/Critic) ra sao về:
     - Độ căn cứ số liệu (**Groundedness** - không ảo giác số).
     - Tính hành động được (**Actionability** - rõ việc, rõ kênh, rõ chỉ số đo).
     - Tính khả thi trong kinh doanh (**Feasibility** - phù hợp nguồn lực SME).

---

## 2. Nguyên Tắc Tránh Rò Rỉ Dữ Liệu (No Data Leakage)
- **Tập kiểm tra bị khóa (Locked Test Set):** Tập test vàng (`gold/test_locked.jsonl`) tuyệt đối **không** được dùng để điều chỉnh prompt, huấn luyện mô hình hay lựa chọn siêu tham số.
- **Phân tách dữ liệu:** Quá trình chuẩn hóa từ điển hay xây dựng đặc trưng TF-IDF chỉ được `fit` trên tập Train/Dev, không áp dụng trên tập Test.
- **Random Seed:** Luôn cố định `random_state = 42` hoặc `seed = 42` trong mọi hàm chia tách (train_test_split), bootstrap hoặc khởi tạo trọng số.

---

## 3. Ý Nghĩa Thống Kê & Khoảng Tin Cậy (Statistical Significance)
- **Không chỉ báo cáo điểm đơn lẻ (Single-point metric):** Mọi kết quả Macro F1, Precision, Recall trên tập test phải đi kèm **Khoảng tin cậy Bootstrap 95%** (Bootstrap Confidence Interval với $B = 1.000$ lần lấy mẫu lại có hoàn lại).
- **Kiểm định độ đồng thuận gán nhãn:** Đánh giá độ tin cậy của tập dữ liệu vàng bằng **Cohen's Kappa** (giữa 2 người gán nhãn) hoặc **Fleiss' Kappa** (từ 3 người gán nhãn trở lên). Bắt buộc đạt $\kappa \ge 0.70$ (substantial agreement).

---

## 4. Đánh Giá Mù (Blind A/B Evaluation) Cho RQ3
- Khi đánh giá chất lượng kế hoạch giữa P0 và P1, nhãn mô hình phải được mã hóa ngẫu nhiên (ví dụ: `Phương án X` vs `Phương án Y`).
- Người đánh giá (hoặc LLM Judge độc lập) chấm điểm trên thang Likert 1–5 theo các tiêu chí chuẩn hóa mà không biết phương án nào đến từ hệ thống đề xuất P1.

---

## 5. Phân Tích Lỗi Hệ Thống (Pareto Error Analysis)
- Không chỉ đưa ra bảng số liệu đẹp, nghiên cứu bắt buộc phải có phần phân tích lỗi sâu:
  - Phân loại lỗi theo quy luật Pareto (80/20): Nhóm 20% nguyên nhân gây ra 80% lỗi.
  - Phân tích ma trận nhầm lẫn (Confusion Matrix) giữa các khía cạnh dễ lẫn (ví dụ: `WATERPROOF` vs `MATERIAL_DURABILITY`).
  - Trích xuất các trường hợp thất bại điển hình (Failure Cases) để thảo luận về giới hạn của hệ thống trong Chương 4 của báo cáo.

<!-- CreBy: MenBoyBMN -->

