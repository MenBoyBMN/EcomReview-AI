---
name: critic-verifier
description: Kiểm định tự động độ tin cậy của Đề xuất Hành động (7 luật R1-R7 kèm Auto-Repair) và Bản nháp Phản hồi CSKH (6 luật G1-G6) trong môi trường Production.
---

# Production Critic & Guardrail Verifier Skill

Kỹ năng này phục vụ kiểm định chất lượng và an toàn nghiệp vụ tự động cho hai đầu ra quan trọng nhất của AI Agent trong **EcomReview AI**: Kế hoạch hành động (`ActionProposal`) và Bản nháp phản hồi khách hàng (`ReplyDraft`).

## 1. Bảy Luật Xác Định Cho Kế Hoạch Hành Động (`HybridCritic` R1–R7)
Triển khai tại `src/ecomreview/agent/critic.py`, kết hợp cơ chế **Auto-Repair** tự động sửa lỗi trước khi xuất ra giao diện:
1. **R1 (Evidence Citation):** Mỗi đề xuất bắt buộc đính kèm tối thiểu 2 mã `evidence_review_ids` hợp lệ có thật trong CSDL.
2. **R2 (Metric Groundedness):** Mọi con số phần trăm hoặc số lượng trong `why_rationale` phải khớp 100% với dữ liệu từ `InsightEngine` / `Aggregator` (`verify_numbers_in_statement()`).
3. **R3 (Marketing vs. Ops Separation):** Nếu `action_type` thuộc `{PRODUCT_FIX, OPS}` thì cờ `is_marketing` bắt buộc là `False`; nếu thuộc `{LISTING_UPDATE, CONTENT, REVIEW_REPLY, PROMOTION, CUSTOMER_CARE}` thì `is_marketing` bắt buộc là `True`.
4. **R4 (Specific Actionability):** Trường `what_to_do` và `how_and_when` phải nêu rõ hành động cụ thể, kênh thực hiện, thời hạn hoàn thành và chỉ số theo dõi (`expected_metric_Watch`).
5. **R5 (SME Feasibility):** Giải pháp phải thiết thực, vừa sức với nhân sự và ngân sách của gian hàng vừa và nhỏ.
6. **R6 (E-commerce Policy Compliance):** Nghiêm cấm các đề xuất vi phạm quy định của Shopee/TikTok Shop (như hối lộ khách xóa đánh giá 1 sao, kéo khách giao dịch ngoài sàn).
7. **R7 (Non-Redundancy):** Không sinh các đề xuất trùng lặp nội dung trong cùng một đợt phân tích.

## 2. Sáu Luật Bảo Vệ Cho Trợ Lý CSKH (`ReplyAssistant` G1–G6)
Triển khai tại `src/ecomreview/agent/reply_assistant.py` để bảo vệ uy tín gian hàng:
1. **G1 (No Overclaiming):** Cấm cam kết phóng đại sai thực tế (*"chống nước 100% vĩnh viễn"*).
2. **G2 (Platform Policy Compliance):** Cấm gạ sửa sao, cấm dẫn khách qua Zalo/Facebook cá nhân.
3. **G3 (PII & Link Safety):** Cấm chèn số điện thoại, email hoặc đường dẫn URL bên ngoài.
4. **G4 (Length Bounds):** Độ dài phản hồi đạt chuẩn từ 40 đến 600 ký tự.
5. **G5 (Negative Aspect Coverage):** Phản hồi trực tiếp vào đúng các khía cạnh mà khách hàng phàn nàn.
6. **G6 (No Unauthorized Monetary Promises):** Cấm tự ý hứa hoàn tiền/tặng tiền với số tiền cụ thể khi chưa có phê duyệt.

<!-- CreBy: MenBoyBMN -->
