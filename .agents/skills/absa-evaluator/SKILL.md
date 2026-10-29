---
name: absa-evaluator
description: Đánh giá hiệu năng bài toán ABSA (Aspect-Based Sentiment Analysis) tiếng Việt với các độ đo Precision, Recall, Macro-F1 và Bootstrap CI 95%.
---

# ABSA Evaluator Skill

Kỹ năng này hướng dẫn thực hiện đánh giá định lượng cho bài toán Phân tích Cảm xúc theo Khía cạnh (ABSA) trên các tập dữ liệu thương mại điện tử tiếng Việt.

## 1. Công Thức Đánh Giá Cốt Lõi
- **Precision, Recall, F1 theo từng Aspect:**
  - True Positive ($TP$): Dự đoán đúng khía cạnh và đúng polarity (Positive, Negative, Neutral).
  - False Positive ($FP$): Dự đoán có khía cạnh nhưng sai polarity, hoặc gán nhầm khía cạnh không có trong ground truth.
  - False Negative ($FN$): Bỏ sót khía cạnh có trong ground truth.
- **Macro-F1 Tổng Thể:** Trung bình cộng điểm F1 trên toàn bộ 8 khía cạnh.

## 2. Quy Trình Tính Bootstrap Confidence Interval (95%)
- Số lần lấy mẫu lại có hoàn lại: $B = 1.000$.
- Cố định seed: `seed=42`.
- Với mỗi lần lấy mẫu $b \in [1, B]$:
  1. Rút ngẫu nhiên $N$ mẫu từ tập test (với $N = \text{len(test)}$).
  2. Tính Macro-F1 trên tập con.
- Xác định phân vị 2.5% và 97.5% để ra khoảng tin cậy: $[F_{1\_low}, F_{1\_high}]$.

## 3. Đầu Ra Bắt Buộc
- Bảng Markdown so sánh Macro F1 giữa các mô hình (B1, B2, B3, A1).
- Ma trận nhầm lẫn (Confusion Matrix) đa nhãn.
- File CSV lưu trữ kết quả chi tiết trong `results/`.

<!-- CreBy: MenBoyBMN -->

