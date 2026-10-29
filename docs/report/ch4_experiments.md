# CHƯƠNG 4: THỰC NGHIỆM, KẾT QUẢ ĐÁNH GIÁ VÀ PHÂN TÍCH LỖI

> **Tài liệu phác thảo khung nội dung — Dự kiến hoàn thiện ở Tuần 4, Tuần 8 & Tuần 9**

## 4.1. Thiết Lập Thực Nghiệm và Chiến Lược Dữ Liệu Kép (Dual-Track Data)
- Tập Benchmark công khai (UIT-ViSFD / VLSP) vs Tập Gold Shop Áo Mưa.
- Quy trình chia tách Train / Val / Test (cố định `seed=42`).
- Phép đo thống kê và kiểm định Bootstrap CI 95% ($B=1.000$).

## 4.2. Kết Quả Thực Nghiệm RQ1: So Sánh Đa Thế Hệ & Hiện Tượng Chuyển Miền
- Bảng tổng hợp Macro-F1 Sentiment 3 lớp và Aspect-Polarity 4 lớp (B1, B2, B3, A1).
- Đánh giá chuyển miền (Domain Shift) sang dữ liệu thực tế Shop Áo Mưa.
- So sánh tốc độ xử lý (Latency) và chi phí vận hành (API Cost).

## 4.3. Kết Quả Thực Nghiệm RQ2: Tác Động Của Module Chuẩn Hóa (Ablation Study)
- Bảng so sánh $\Delta\text{Macro-F1}$ khi Bật / Tắt Normalizer.
- Phân tích hiệu năng trên 3 lát cắt dữ liệu: `has_teencode`, `is_no_diacritics`, `has_emoji`.

## 4.4. Kết Quả Thực Nghiệm RQ3: Đánh Giá Kiến Trúc AI Agent
- Đánh giá tính căn cứ tự động: Tỷ lệ nhất quán số liệu (Number Consistency = 100%), tính hợp lệ bằng chứng (Evidence Validity), độ trung thực trích dẫn (Quote Fidelity).
- Kết quả Đánh giá Mù (Blind Evaluation) từ chuyên gia theo Rubric 5 tiêu chí (So sánh P0 vs P1).
- Mô phỏng quy trình nghiệp vụ Case Study trên 10 kịch bản thực tế của Shop Áo Mưa.

## 4.5. Phân Tích Lỗi Hệ Thống Theo Nguyên Lý Pareto (Pareto Error Analysis)
- Phân loại 10 nhóm lỗi (E1–E10) trong ABSA và Agent Planning.
- Biểu đồ Pareto và bài học kinh nghiệm.

<!-- CreBy: MenBoyBMN -->
