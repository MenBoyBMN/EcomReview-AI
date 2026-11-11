# Chương 4 (Phần 2): Kết Quả Thực Nghiệm RQ3 — Đánh Giá Tam Giác Kiến Trúc Tác Tử (`P0` vs `P1-no-Critic` vs `P1-Full`), Chấm Mù A/B Và Case Study Shop Áo Mưa

---

## 4.4. Kết Quả Nghiên Cứu RQ3 (Hướng 1): Đánh Giá Tự Động Độ Bám Sát Bằng Chứng & Thực Nghiệm Cắt Bỏ Critic (`Automated Groundedness & Critic Ablation`)

Để trả lời câu hỏi nghiên cứu **RQ3**: *"Kiến trúc tác tử đa chặng kết hợp bộ tổng hợp thống kê SQL/Wilson 95% CI và bộ phản biện lai 7 quy tắc xác định (`HybridCritic` R1–R7) cải thiện mức độ bám sát bằng chứng (`Groundedness`), tính nhất quán số học (`Numeric Consistency`) và độ an toàn chính sách như thế nào so với tác tử một bước (`Single-Prompt Agent`)?"*, hệ thống thực hiện đối sánh định lượng trên **10 kịch bản kinh doanh thực tế ($S_1 \dots S_{10}$, tổng cộng 30 bộ kế hoạch hành động)** giữa 3 cấu hình:
1. **`P0_Single_Prompt` (Baseline Agent):** Tác tử gọi trực tiếp LLM một bước từ tập đánh giá thô, không thông qua SQL Aggregator và không có vòng lặp phản biện `HybridCritic`.
2. **`P1_No_Critic` (Ablation — Iteration 0):** Tác tử có sử dụng SQL Aggregator, `InsightEngine` và `ActionPlanner` dựa trên `playbook_aomua.yaml`, nhưng **tắt** vòng lặp kiểm định `HybridCritic` R1–R7 và cơ chế `auto_repair`.
3. **`P1_Full_Proposed` (Proposed State-Graph Agent):** Kiến trúc đề xuất hoàn chỉnh tích hợp vòng lặp `ActionPlanner <-> HybridCritic (R1–R7)` và chốt chặn sửa lỗi xác định `auto_repair`.

Kết quả thực nghiệm trên 5 chỉ số định lượng tự động kèm khoảng tin cậy **Bootstrap 95% CI** ($B = 2.000, \text{seed} = 42$, trích xuất từ `results/rq3_automated.csv`) được trình bày tại **Bảng 4.4**:

| Hệ thống / Cấu hình Tác tử | Evidence Validity (%) (95% CI) | Numeric Consistency (%) (95% CI) | Quote Fidelity (%) (95% CI) | Structural Completeness (%) (95% CI) | Policy & Claim Safety (%) (95% CI) | Điểm Critic (`/5.0`) (95% CI) | Tỷ lệ Vượt R1–R7 (`Pass Rate`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`P0_Single_Prompt` (Baseline)** | `0.00 [0.00 - 0.00]` | `0.00 [0.00 - 0.00]` | `100.00 [100.00 - 100.00]` | `66.67 [66.67 - 66.67]` | `33.33 [33.33 - 33.33]` | `1.00 [1.00 - 1.00]` | `0.0% (0/10)` |
| **`P1_No_Critic` (Ablation — Vòng 0)** | **`100.00 [100.00 - 100.00]`** | `51.67 [46.67 - 56.67]` | `100.00 [100.00 - 100.00]` | **`100.00 [100.00 - 100.00]`** | **`100.00 [100.00 - 100.00]`** | `3.87 [3.62 - 4.00]` | `0.0% (0/10)` |
| **`P1_Full_Proposed` (Đề xuất)** | **`100.00 [100.00 - 100.00]`** | **`100.00 [100.00 - 100.00]`** | **`100.00 [100.00 - 100.00]`** | **`100.00 [100.00 - 100.00]`** | **`100.00 [100.00 - 100.00]`** | **`5.00 [5.00 - 5.00]`** | **`100.0% (10/10)`** |

**Phân tích học thuật từ Bảng 4.4:**
1. **Sự sụp đổ của Tác tử Một Bước (`P0_Single_Prompt`) trước yêu cầu xác thực số học và an toàn chính sách:**
   - Do không có SQL Aggregator cung cấp thống kê chuẩn, `P0` tự suy diễn các con số phần trăm ước lượng cảm tính (như *"Khoảng 85% khách hàng phàn nàn..."*), dẫn đến **Numeric Consistency = `0.00%`** và **Evidence Validity = `0.00%`** (gắn mã `insight_ids` giả định `unverified_1`).
   - Nghiêm trọng hơn, `P0` thường xuyên sinh các lời khuyên chiều lòng người dùng nhưng vi phạm rào chắn ngành hàng: cam kết *"chống thấm 100% tuyệt đối"* (vi phạm **R4**), thiếu mốc thời gian hoàn thành (vi phạm **R3**, khiến Structural Completeness chỉ đạt `66.67%`), và gán sai cờ `is_marketing` cho hành động sửa lỗi sản phẩm (vi phạm **R5**, khiến Policy & Claim Safety chỉ đạt `33.33%`).
2. **Vai trò quyết định của `HybridCritic` R1–R7 trong thực nghiệm cắt bỏ (`P1_No_Critic` vs `P1_Full_Proposed`):**
   - Khi bổ sung SQL Aggregator và Playbook (`P1_No_Critic`), các chỉ số `Evidence Validity`, `Structural Completeness` và `Policy Safety` lập tức tăng lên **`100.00%`**.
   - Tuy nhiên, ở vòng khởi tạo đầu tiên (`Iteration 0`), khi một kịch bản có nhiều nhận định kinh doanh (`Insights`), `ActionPlanner` có hiện tượng tham chiếu chéo lệch chỉ mục giữa `insight_ids` và câu `why_rationale`, làm `Numeric Consistency` chỉ đạt **`51.67% [46.67 - 56.67]`** và điểm Critic dừng ở `3.87 / 5.0`.
   - Khi kích hoạt **`HybridCritic` (Luật R2 — Numeric Grounding) và `auto_repair`** trong `P1_Full_Proposed`, toàn bộ các sai lệch liên kết số học được phát hiện và đồng bộ hóa 100%, đưa **Numeric Consistency tăng vọt `+48.33%` lên mức tuyệt đối `100.00%`**, đạt **Pass Rate = `100.0%` (10/10 kịch bản)** và điểm Critic tuyệt đối **`5.00 / 5.00`**.

---

## 4.5. Kết Quả Nghiên Cứu RQ3 (Hướng 2): Đánh Giá Chấm Mù A/B Theo Rubric 5 Tiêu Chí & Mô Phỏng Phê Duyệt Nghiệp Vụ (`Blind A/B & SME Adoption`)

### 4.5.1. Kết Quả Chấm Mù A/B Trên 5 Tiêu Chí Rubric (`C1 – C5`)
Hai mươi bộ đề xuất (`10 kịch bản × {P0, P1}`) được ẩn danh và xáo trộn ngẫu nhiên thành Phương án A / Phương án B trong `results/blind_ab_pack.md` (`seed = 42`). Kết quả giải mã và tính khoảng tin cậy **Bootstrap 95% CI** trên thang điểm Likert $1.0\text{--}5.0$ (trích xuất từ `results/rq3_simulation_ratings.csv` và `results/rq3_final_summary.csv`) được tổng hợp tại **Bảng 4.5**:

| Tiêu Chí Rubric (Thang điểm 1.0 – 5.0) | `P0_Single_Prompt` (Mean & 95% CI) | `P1_Full_Proposed` (Mean & 95% CI) | Mức Cải Thiện ($\Delta$) |
| :--- | :---: | :---: | :---: |
| **C1: Tính Cụ Thể Ngành Hàng (`Specificity`)** | `3.00 [3.00 - 3.00]` | **`4.90 [4.70 - 5.00]`** | **`+1.90`** |
| **C2: Tính Khả Thi Cho SME (`Actionability for SME`)** | `3.33 [3.33 - 3.33]` | **`5.00 [5.00 - 5.00]`** | **`+1.67`** |
| **C3: Độ Bám Sát Dữ Liệu (`Data Relevance`)** | `1.50 [1.50 - 1.50]` | **`5.00 [5.00 - 5.00]`** | **`+3.50`** |
| **C4: Bằng Chứng & Sức Thuyết Phục (`Evidence`)** | `2.00 [2.00 - 2.00]` | **`5.00 [5.00 - 5.00]`** | **`+3.00`** |
| **C5: An Toàn Chính Sách & Thực Tế (`Safety & Realism`)** | `1.00 [1.00 - 1.00]` | **`5.00 [5.00 - 5.00]`** | **`+4.00`** |
| **Điểm Trung Bình Tổng Hợp (`Overall Rubric Score`)** | `2.17 [2.17 - 2.17]` | **`4.98 [4.94 - 5.00]`** | **`+2.81`** |
| **Tỷ Lệ Thắng Chấm Mù A/B (`Blind A/B Win Rate`)** | `0.0% (0/10 kịch bản)` | **`100.0% (10/10 kịch bản)`** | **`+100.0%`** |

### 4.5.2. Kết Quả Mô Phỏng Quy Trình Duyệt Nghiệp Vụ Của Chủ Shop (`Human-in-the-Loop Adoption`)
Trên toàn bộ **29 đề xuất hành động** do hệ thống `P1_Full_Proposed` sinh ra trên tập dữ liệu thực tế `real_shop` (5 hành động) và 10 kịch bản $S_1 \dots S_{10}$ (24 hành động), kết quả mô phỏng quyết định phê duyệt tại cổng Human-in-the-Loop (lưu tại `results/rq3_adoption.csv`) đạt được như sau (**Bảng 4.6**):

| Quyết Định Phê Duyệt (`Decision`) | Số Lượng Hành Động (`n / 29`) | Tỷ Lệ Phần Trăm (`%`) | Khoảng Cách Chỉnh Sửa Trung Bình (`edit_distance_chars`) | Ghi Chú Nghiệp Vụ Điển Hình |
| :--- | :---: | :---: | :---: | :--- |
| **`APPROVED` (Duyệt áp dụng ngay)** | `26 / 29` | **`89.66%`** | `0.0 ký tự` | Đề xuất cụ thể, đúng lỗi kỹ thuật áo mưa (ép nhiệt đáy quần, nẹp khóa 2 lớp, bảng size balo), số liệu chuẩn xác 100%. |
| **`EDITED` (Chỉnh sửa nhẹ rồi duyệt)** | `2 / 29` | **`6.90%`** | `57.0 ký tự` | Giữ nguyên giải pháp gốc, chỉ bổ sung trần ngân sách voucher (`tối đa 10.000đ/đơn`) cho phù hợp biên lợi nhuận shop nhỏ. |
| **`REJECTED` (Từ chối / Tạm hoãn)** | `1 / 29` | **`3.45%`** | `N/A` | Tạm hoãn hành động rà soát chung ở nhóm `GENERAL` để ưu tiên nguồn lực xử lý lỗi cốt lõi trong tuần. |
| **Tổng Tỷ Lệ Chấp Nhận Sử Dụng (`Usable Adoption = APPROVED + EDITED`)** | **`28 / 29`** | **`96.55%`** | — | **Vượt xa kỳ vọng giả thuyết nghiên cứu $H_3$ ($\ge 80\%$)** |

---

## 4.6. Kết Quả Nghiên Cứu RQ3 (Hướng 3): Nghiên Cứu Tình Huống Thực Tế Trên Gian Hàng Áo Mưa (`Real-Shop Case Study`)

Khi vận hành thực tế trên tập dữ liệu **`real_shop` (150 đánh giá Shopee & TikTok Shop, chi tiết trong `docs/case_study_shop_aomua.md`)**, hệ thống **EcomReview AI** đã chứng minh giá trị thực tiễn rõ rệt qua 3 khía cạnh:
1. **Phát hiện điểm mù dữ liệu mà con người bỏ sót:** Hệ thống tự động bóc tách được **23 phàn nàn ẩn (`HIDDEN_COMPLAINT` = 17.0%, Wilson 95% CI: `[11.6% - 24.3%]`)** nằm ẩn trong 135 đánh giá 4–5 sao (khách khen giao nhanh và màu Pastel đẹp nhưng phàn nàn mùi nhựa mới hoặc đường may đáy quần bị thấm khi mưa lớn), đồng thời chỉ ra **chênh lệch trải nghiệm giữa hai sàn (`PLATFORM_GAP` = 47.3%)** giữa Shopee (`55.6%` tiêu cực) và TikTok Shop (`8.3%` tiêu cực).
2. **Chuyển hóa trực tiếp thành 5 hành động thực thi trên sàn:** Cả 5 đề xuất của `P1` cho `real_shop` (từ làm video ngắn test độ bền vải dù tổ ong `act_001`, đưa ảnh bộ sưu tập màu Pastel & dải phản quang lên đầu trang `act_002`, bổ sung Infographic hướng dẫn gài nẹp chắn nước 2 lớp ở ảnh số 3 `act_003`, đến quy trình phơi khử mùi nhựa 24h tại kho `act_004` và gia cố băng keo ép nhiệt đáy quần `act_005`) đều được phê duyệt `APPROVED` 100%.
3. **Rút ngắn hơn 95% thời gian tác nghiệp:** Thời gian để chủ shop SME hoàn tất chu trình từ đọc hiểu 150 đánh giá, tính toán thống kê đa chiều đến lập kế hoạch hành động giảm từ **~135–180 phút làm thủ công xuống chỉ còn ~5 phút** thao tác duyệt trên giao diện Streamlit Dashboard.

<!-- CreBy: MenBoyBMN -->

