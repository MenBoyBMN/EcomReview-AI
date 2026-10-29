---
name: critic-verifier
description: Kiểm định độ tin cậy và tuân thủ 7 luật xác định (R1-R7) của các đề xuất hành động marketing sinh bởi AI Agent.
---

# Critic Verifier Skill

Kỹ năng này phục vụ kiểm định và phát hiện lỗi tự động đối với các đề xuất hành động (`ActionProposal`) được tạo ra từ `Action Planner`.

## 1. Danh Mục 7 Luật Xác Định (Deterministic Rules)
1. **R1 (Evidence Citation):** Mỗi đề xuất phải gắn kèm tối thiểu 2 `evidence_review_ids` thực tế từ cơ sở dữ liệu.
2. **R2 (Metric Groundedness):** Mọi con số trong `why_rationale` (ví dụ: "chiếm 18.5%", "tăng 12 review") phải khớp 100% với dữ liệu từ `InsightEngine` hoặc `Aggregator`.
3. **R3 (Marketing vs Ops Separation):** Nếu `action_type` thuộc `{PRODUCT_FIX, OPS}`, cờ `is_marketing` bắt buộc là `False`. Ngược lại phải là `True`.
4. **R4 (Actionability):** Trường `what_to_do` và `how_and_when` phải chứa động từ hành động cụ thể và mốc thời gian rõ ràng (ví dụ: "trong 3 ngày", "trước đợt bão thứ Sáu").
5. **R5 (Budget & Feasibility):** Không đề xuất các chiến dịch quảng cáo hoặc thiết bị vượt quá năng lực của cửa hàng nhỏ (SME).
6. **R6 (E-commerce Policy Compliance):** Nghiêm cấm các đề xuất vi phạm chính sách của Shopee/TikTok Shop (như gạ khách xóa 1 sao để được đổi trả, hướng dẫn giao dịch ngoài sàn).
7. **R7 (Non-Redundancy):** Không sinh các đề xuất trùng lặp mục tiêu trong cùng một phiên chạy State-Graph.

## 2. Tiêu Chí Đánh Giá Của LLM-Judge (Thang Điểm 1-5)
- **Score 1:** Hoang tưởng, bịa số liệu, vi phạm chính sách sàn nghiêm trọng.
- **Score 3:** Số liệu đúng nhưng đề xuất chung chung, thiếu tính hành động.
- **Score 5:** Tuyệt đối chính xác, bám sát tri thức miền áo mưa, có giá trị kinh doanh cao.

<!-- CreBy: MenBoyBMN -->

