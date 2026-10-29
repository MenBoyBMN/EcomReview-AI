# CHƯƠNG 3: PHƯƠNG PHÁP ĐỀ XUẤT VÀ THIẾT KẾ KIẾN TRÚC HỆ THỐNG

> **Tài liệu phác thảo khung nội dung — Dự kiến hoàn thiện ở Tuần 3, Tuần 5, Tuần 6 & Tuần 7**

## 3.1. Tổng Quan Kiến Trúc Toàn Hệ Thống (End-to-End Pipeline)
- Quy trình dòng dữ liệu từ raw reviews $\rightarrow$ Clean $\rightarrow$ ABSA $\rightarrow$ PostgreSQL $\rightarrow$ Agent State-Graph $\rightarrow$ Dashboard.
- Kiến trúc an toàn 4 lớp chống Prompt Injection.

## 3.2. Chuẩn Hóa Văn Bản Tiếng Việt Mạng Xã Hội (Vietnamese Social Text Normalizer)
- Từ điển Teencode quy chuẩn (200+ từ).
- Rút gọn ký tự kéo dài (`đẹppppp` $\rightarrow$ `đẹp`).
- Chuyển đổi Emoji sang nhãn cảm xúc dạng text.
- Chuẩn hóa Unicode dựng sẵn (NFC).

## 3.3. Các Mô Hình Phân Tích Cảm Xúc Theo Khía Cạnh (ABSA)
- **Baseline 1 (B1):** Rule-based Lexicon + Window-based matching.
- **Baseline 2 (B2):** TF-IDF Character/Word N-grams + Multi-output Logistic Regression.
- **Baseline 3 (B3):** Pretrained ViSoBERT Fine-tuned.
- **Proposed Analyzer (A1):** Gemini Flash Few-shot với Pydantic Structured Output.

## 3.4. Cơ Sở Dữ Liệu PostgreSQL & Module Tính Toán Xác Thực (Aggregator Engine)
- Thiết kế lược đồ quan hệ: Bảng `reviews`, `aspect_opinions`, `insights`, `action_proposals`, `critic_reviews`.
- Thuật toán thống kê xác định & Khoảng tin cậy Wilson Score Interval.

## 3.5. Kiến Trúc AI Agent State-Graph & Thẩm Định Lai (Hybrid Critic)
- Sơ đồ chuyển trạng thái: `Aggregator` $\rightarrow$ `Insight Engine` $\rightarrow$ `Action Planner` $\rightleftarrows$ `Hybrid Critic`.
- Bộ 7 quy tắc Critic xác định (R1–R7) + LLM-Judge.
- Cơ chế Human-in-the-Loop Approval Gate.

<!-- CreBy: MenBoyBMN -->

