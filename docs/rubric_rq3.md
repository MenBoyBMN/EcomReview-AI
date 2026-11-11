# Rubric Đánh Giá Chất Lượng Kế Hoạch Hành Động Marketing & Vận Hành (RQ3 Evaluation Rubric)

Tài liệu này định nghĩa **Rubric 5 tiêu chí (C1 – C5)** trên thang điểm **Likert 1 – 5** để phục vụ quy trình **Chấm mù A/B (Blind A/B Evaluation)** và **Mô phỏng Nghiệp vụ Chủ Shop SME (Simulated Business Workflow)** đối với câu hỏi nghiên cứu **RQ3**.

---

## 1. Quy Tắc Chấm Mù A/B (Blind A/B Protocol)

- Trên mỗi kịch bản kinh doanh ($S_1 \dots S_{10}$), bộ đề xuất của hai hệ thống **`P0 (Single-Prompt Baseline)`** và **`P1 (Proposed State-Graph + HybridCritic)`** được chuẩn hóa về cùng một biểu mẫu hiển thị trung lập (ẩn hoàn toàn tên hệ thống, điểm Critic và siêu dữ liệu kỹ thuật).
- Hai bộ đề xuất được xáo trộn ngẫu nhiên với `seed = 42` thành **Phương án A** và **Phương án B** trong tài liệu `results/blind_ab_pack.md`. Khóa giải mã được niêm phong riêng tại `results/secret_key.json`.
- Người đánh giá (đóng vai chủ gian hàng Áo mưa trên Shopee / TikTok Shop) chấm điểm độc lập từng phương án theo 5 tiêu chí `C1 – C5` dưới đây và chọn phương án ưu tiên (`A`, `B`, hoặc `Tie`).

---

## 2. Chi Tiết 5 Tiêu Chí Đánh Giá (Thang Điểm Likert 1 – 5)

| Mã | Tiêu Chí | Trọng Tâm Đánh Giá | Mức 1 (Rất Kém) | Mức 3 (Trung Bình) | Mức 5 (Xuất Sắc) |
| :-: | :--- | :--- | :--- | :--- | :--- |
| **C1** | **Tính Cụ Thể (Specificity)** | Hành động có nêu rõ đối tượng, bộ phận sản phẩm (đường ép nhiệt đáy quần, cúc bấm, kính chắn mưa, tà sau phủ balo) và bước thực thi rõ ràng hay không? | Khuyên chung chung kiểu *"Nâng cao chất lượng sản phẩm và dịch vụ khách hàng"*. | Có nhắc đến khía cạnh bị phàn nàn nhưng giải pháp còn mang tính khẩu hiệu. | Chỉ rõ chính xác vị trí lỗi/điểm mạnh, kênh triển khai (ảnh bìa Shopee, video TikTok, tin nhắn tự động) và nội dung cần làm. |
| **C2** | **Tính Khả Thi Cho SME (Actionability for SME)** | Chủ shop nhỏ (1–3 nhân sự) có thể thực hiện ngay với nguồn lực hạn chế và mốc thời gian (`how_and_when`) rõ ràng hay không? | Đề xuất viển vông (đòi xây nhà máy mới, thay đổi toàn bộ dây chuyền lớn) hoặc không có thời hạn thực hiện. | Khả thi nhưng thiếu thời hạn hoàn thành cụ thể hoặc thiếu chỉ số đo lường KPI (`success_metric`). | Có đầy đủ 4 thành phần (`What`, `Why`, `How/When` kèm mốc giờ/ngày cụ thể như `24h`, `48h`, `7 ngày`, và `KPI` đo được). |
| **C3** | **Độ Bám Sát Dữ Liệu (Data Relevance & Numeric Grounding)** | Lý do đề xuất (`why_rationale`) có trích dẫn đúng số lượng, tỷ lệ phần trăm và khoảng tin cậy Wilson 95% CI từ dữ liệu thực tế của kịch bản hay không? | Bịa đặt số liệu thống kê (ví dụ: tự bịa `"85% khách hàng phàn nàn"` không khớp CSDL) hoặc không có số liệu. | Nhắc đúng xu hướng tăng/giảm nhưng số liệu làm tròn sai lệch hoặc lấy nhầm sang khía cạnh khác. | 100% con số thống kê (số lượng, tỷ lệ %, khoảng tin cậy 95% CI) khớp tuyệt đối với kết quả truy vấn SQL của Insight gốc. |
| **C4** | **Tính Thuyết Phục Của Bằng Chứng (Evidence & Persuasiveness)** | Đề xuất có gắn kèm tối thiểu 2 mã đánh giá thực tế (`evidence_review_ids`) có thật trong CSDL và trích dẫn nguyên văn tiếng nói khách hàng hay không? | Không dẫn chứng được mã review nào, hoặc bịa mã `review_id` không tồn tại (`hallucinated IDs`). | Có gắn mã review nhưng chỉ có 1 mã hoặc nội dung review không sát với hành động đề xuất. | Gắn kèm $\ge 2$ mã `review_id` thực tế, đa dạng (đã lọc trùng lặp Jaccard $\le 0.70$) và phản ánh trực tiếp nguyên nhân gốc rễ. |
| **C5** | **Độ An Toàn Chính Sách & Thực Tế (Policy & Claim Safety)** | Đề xuất có tuân thủ chính sách sàn TMĐT (Shopee/TikTok Shop) và tránh cam kết quá đà gây rủi ro pháp lý/trả hàng hay không? | Vi phạm nghiêm trọng: xúi giục *"tặng tiền đổi 5 sao"*, *"gạ khách xóa đánh giá 1 sao"* (vi phạm R7) hoặc quảng cáo lố *"chống thấm 100% vĩnh viễn"* (vi phạm R4). | Không vi phạm chính sách sàn nhưng phân loại nhầm giữa hành động Marketing và Vận hành/Sản phẩm (vi phạm R5). | Tuân thủ tuyệt đối 7 quy tắc bảo vệ R1–R7: trung thực về giới hạn kỹ thuật của áo mưa, an toàn chính sách sàn và phân tách đúng `is_marketing`. |

---

## 3. Quy Trình Mô Phỏng Phê Duyệt Nghiệp Vụ (Human-in-the-Loop Adoption Workflow)

Bên cạnh chấm mù A/B, toàn bộ các đề xuất hành động của hệ thống **`P1`** trên 10 kịch bản ($S_1 \dots S_{10}$) và tập dữ liệu thực tế **`real_shop`** được đưa qua cổng phê duyệt nghiệp vụ (tương ứng Trang 3 — *Kế Hoạch Hành Động & Phê Duyệt* trên Streamlit Dashboard) với 3 quyết định:
1. **`APPROVED` (Duyệt áp dụng ngay):** Đề xuất chính xác, khả thi, giữ nguyên 100% nội dung (`edit_distance_chars = 0`).
2. **`EDITED` (Chỉnh sửa nhẹ rồi duyệt):** Đề xuất đúng hướng nhưng chủ shop tinh chỉnh lại câu chữ/mức giảm giá cho sát thực tế vận hành (`edit_distance_chars > 0`).
3. **`REJECTED` (Từ chối):** Đề xuất chưa phù hợp tại thời điểm hiện tại (ghi rõ lý do từ chối vào bảng kiểm toán `action_feedback`).

<!-- CreBy: MenBoyBMN -->

