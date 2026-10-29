---
name: academic-report-helper
description: Hỗ trợ biên soạn và rà soát báo cáo nghiên cứu khoa học 30-50 trang theo chuẩn học thuật (IEEE/ACM/Đại học).
---

# Academic Report Helper Skill

Kỹ năng này định hướng cấu trúc, văn phong và phương pháp tổng hợp cho báo cáo nghiên cứu khoa học 30–50 trang của dự án **EcomReview AI**.

## 1. Cấu Trúc Báo Cáo 5 Chương Chuẩn Mực

- **Chương 1: Mở Đầu (3–5 trang)**
  - Bối cảnh TMĐT Việt Nam & phản hồi khách hàng dạng văn bản tự do.
  - Tuyên bố bài toán & thách thức thực tế của SMEs.
  - 3 Câu hỏi nghiên cứu (RQ1, RQ2, RQ3).
  - Đóng góp chính của đề tài.

- **Chương 2: Tổng Quan Công Trình Liên Quan (5–8 trang)**
  - Tối thiểu 15–25 công trình học thuật (ABSA tiếng Việt, LLM Zero-shot, AI Agent trong Marketing).
  - Bảng tổng hợp so sánh phương pháp và khoảng trống nghiên cứu (Research Gap).

- **Chương 3: Phương Pháp & Kiến Trúc Hệ Thống (8–12 trang)**
  - Chiến lược dữ liệu kép (Benchmark UIT-ViSFD + Shop Áo Mưa).
  - Quy trình tiền xử lý teencode và an toàn Prompt Injection 4 lớp.
  - Các mô hình Baseline (B1, B2, B3) & Mô hình đề xuất A1 (Gemini Flash).
  - Kiến trúc State-Graph Agent thuần: Aggregator $\rightarrow$ Insight $\rightarrow$ Planner $\rightleftarrows$ Hybrid Critic.

- **Chương 4: Thực Nghiệm, Kết Quả & Thảo Luận (10–15 trang)**
  - Thiết lập thực nghiệm, độ đo Macro F1 và Bootstrap CI 95%.
  - Kết quả trả lời RQ1, RQ2 và Ablation study.
  - Đánh giá mù RQ3 (P0 vs P1), đo Groundedness & Actionability.
  - Phân tích lỗi theo nguyên lý Pareto (80/20) và thảo luận giới hạn hệ thống.

- **Chương 5: Kết Luận & Hướng Phát Triển (2–3 trang)**
  - Tóm tắt kết quả đạt được.
  - Đóng góp thực tiễn cho cửa hàng vừa và nhỏ.
  - Hạn chế và hướng mở rộng tương lai.

## 2. Tiêu Chuẩn Trích Dẫn & Văn Phong
- **Văn phong:** Khách quan, trung lập, dùng thể thụ động hoặc ngôi thứ ba, lập luận dựa trên số liệu thực nghiệm.
- **Trích dẫn:** Đúng quy cách chuẩn APA hoặc IEEE, đầy đủ tác giả, năm công bố và nguồn DOI/ArXiv.

<!-- CreBy: MenBoyBMN -->

