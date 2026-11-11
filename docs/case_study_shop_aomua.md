# Nghiên Cứu Tình Huống Thực Tế (Case Study): Tối Ưu Hóa Gian Hàng Áo Mưa Trên Shopee & TikTok Shop

Tài liệu này ghi nhận kết quả triển khai thực nghiệm luồng công việc đầu-cuối (End-to-End Case Study) của hệ thống **EcomReview AI (`P1_Full_Proposed`)** trên tập dữ liệu thực tế **`real_shop` (Shop Áo Mưa — 150 đánh giá thương mại điện tử)** nhằm kiểm chứng **Tính Khả Thi Vận Hành (Operational Feasibility)** cho doanh nghiệp nhỏ và vừa (SMEs).

---

## 1. Bối Cảnh Gian Hàng & Thách Thức Trước Khi Áp Dụng

- **Sản phẩm trọng tâm:** Bộ áo mưa vải dù tổ ong / da cá cao cấp và áo mưa cánh dơi thời trang màu Pastel Hàn Quốc có dải phản quang sau lưng, kinh doanh đồng thời trên **Shopee** và **TikTok Shop**.
- **Quy trình thủ công trước đây (Baseline Manual Process):**
  - Chủ shop (nhân sự vận hành 1–2 người) phải tự đọc lướt hàng trăm đánh giá mỗi tuần trên cả hai sàn.
  - **Các điểm mù nghiêm trọng:**
    1. Không phát hiện được **23 phàn nàn ẩn (17.0%)** nằm lẫn bên trong 135 đánh giá 4–5 sao (khách hàng vẫn chấm 5 sao vì giao nhanh nhưng than phiền trong bình luận rằng *"vải hơi mỏng, có mùi nhựa mới"* hoặc *"đi mưa to bị ngấm nước ở đường may đáy quần"*).
    2. Không định lượng được mức độ nghiêm trọng thực sự của lỗi chống thấm (`WATERPROOF` có tỷ lệ tiêu cực lên tới **50.0%**, khoảng tin cậy Wilson 95% CI từ **29.0% đến 71.0%** trên 18 phản hồi).
    3. Không nhận ra **chênh lệch trải nghiệm giữa hai sàn (`PLATFORM_GAP` = 47.3%)** ở khía cạnh `MATERIAL_DURABILITY` (Shopee chịu tỷ lệ tiêu cực 55.6% do mô tả bài viết cũ chưa rõ chất vải, trong khi TikTok Shop chỉ có 8.3% tiêu cực nhờ khách được xem trực tiếp trên Livestream).

---

## 2. Kết Quả Chẩn Đoán Tự Động Từ EcomReview AI (`real_shop`)

Khi chạy pipeline **EcomReview AI** trên kịch bản `real_shop`, hệ thống hoàn tất phân tích và lập kế hoạch trong **`73.84 ms`** (chế độ Cache/SQLite), tự động trích xuất **7 Insights kinh doanh** thuộc đủ 5 nhóm và sinh **5 Đề xuất Hành động (`act_001` – `act_005`)** vượt qua 100% 7 quy tắc `HybridCritic` R1–R7 (Điểm Critic = `5.0 / 5.0`):

| Mã Hành Động | Phân Nhóm | Tiêu Đề Đề Xuất | Điểm Ưu Tiên | Mã Review Bằng Chứng Thực Tế | Quyết Định Chủ Shop |
| :-: | :-: | :--- | :-: | :--- | :-: |
| `act_001` | `CONTENT` *(Marketing)* | Sản xuất video TikTok/Reels test độ dẻo dai vải dù tổ ong / da cá | `4.24` (HIGH) | `tts_0205`, `tts_0008`, `tts_0042`, `tts_0024` | ✅ `APPROVED` |
| `act_002` | `CONTENT` *(Marketing)* | Làm nổi bật bộ sưu tập màu Pastel Hàn Quốc và dải phản quang an toàn ban đêm | `3.80` (HIGH) | `tts_0243`, `tts_0156`, `dev_syn_0013`, `dev_syn_0021` | ✅ `APPROVED` |
| `act_003` | `LISTING_UPDATE` *(Marketing)* | Cập nhật hướng dẫn gài nẹp chắn nước 2 lớp trên ảnh mô tả sản phẩm | `3.00` (HIGH) | `tts_0053`, `tts_0024`, `tts_0179`, `tts_0096` | ✅ `APPROVED` |
| `act_004` | `OPS` *(Vận hành)* | Khử mùi nhựa PVC/PU và kiểm tra độ bền khuy bấm trước khi đóng gói | `2.83` (HIGH) | `tts_0052`, `dev_syn_0017`, `dev_syn_0012`, `dev_syn_0022` | ✅ `APPROVED` |
| `act_005` | `PRODUCT_FIX` *(Sản phẩm)* | Gia cố băng keo ép nhiệt đường may đáy quần và nẹp khóa kéo | `2.05` (MEDIUM) | `tts_0053`, `tts_0024`, `tts_0179`, `tts_0096` | ✅ `APPROVED` |

---

## 3. Minh Chứng Triển Khai Trước & Sau (Before / After Implementation)

### Hạng mục 1: Cập nhật Trang Sản Phẩm Shopee/TikTok Shop (`LISTING_UPDATE` — `act_003` & `act_002`)

| Tiêu Chí | TRƯỚC KHI ÁP DỤNG (Before) | SAU KHI ÁP DỤNG ECOMREVIEW AI (After) |
| :--- | :--- | :--- |
| **Hình ảnh & Infographic mô tả** | Chỉ có ảnh mẫu mặc áo mưa chụp trong studio; thiếu hướng dẫn gài nẹp chắn nước 2 lớp và bảng chọn size khi đeo balo. | **Ảnh bìa & Ảnh số 2:** Đưa ảnh thực tế bộ sưu tập màu Pastel Hàn Quốc kèm hiệu ứng dải phản quang ban đêm (tận dụng điểm mạnh `ACCESSIBILITY_DESIGN` đạt **94.4% tích cực [81.9% – 98.5%]**).<br>**Ảnh số 3 (Infographic mới):** Hướng dẫn trực quan 2 bước *"Kéo kín khóa kéo trong + Bấm khít hàng cúc nẹp ngoài"* để ngăn nước mưa tạt ngang ngực khi đi xe máy và bảng chọn tăng 1 size khi đeo balo. |
| **Cam kết quảng cáo trên tiêu đề/mô tả** | Dùng từ ngữ cảm tính dễ gây hiểu lầm (*"Áo mưa chống thấm tuyệt đối 100%"*), dẫn đến khách hàng bức xúc khi đi mưa bão lớn bị ngấm đường may. | Tuân thủ chặt chẽ **Luật R4 (`No Overclaiming`)**: Mô tả trung thực thông số vải dù tráng PU chống thấm nước mưa rào, kèm hướng dẫn bảo quản băng keo ép nhiệt (`seam tape`) không giặt máy/vắt mạnh. |

### Hạng mục 2: Chuẩn Hóa Kịch Bản Chăm Sóc Khách Hàng & Xử Lý Phàn Nàn Ẩn (`REVIEW_REPLY` / `OPS` — `act_004` & `act_005`)

- **Trước khi áp dụng:** Shop chỉ trả lời tự động mẫu câu chung chung (*"Cảm ơn bạn đã ủng hộ shop ạ"*) cho mọi đánh giá 5 sao, bỏ lọt hoàn toàn 23 khách hàng phàn nàn ẩn về mùi nhựa mới và đường ép nhiệt.
- **Sau khi áp dụng:**
  1. **Tại kho đóng gói (`act_004`):** Áp dụng quy trình phơi thoáng khí lô áo mưa mới nhập 24 giờ và kiểm tra lực bấm hàng khuy trước khi đóng túi gửi đi.
  2. **Phản hồi đánh giá có căn cứ & an toàn chính sách (`R7`):** Với các đánh giá phản ánh thấm nước đường may (`tts_0053`, `tts_0024`, `tts_0179`, `tts_0096`), shop chủ động phản hồi hướng dẫn kiểm tra lớp băng keo ép nhiệt đáy quần và hỗ trợ đổi mới miễn phí qua hệ thống trả hàng/đổi hàng chính thức của sàn (tuyệt đối không gạ khách xóa đánh giá hay giao dịch ngoài sàn).

---

## 4. Đánh Giá Hiệu Quả Vận Hành (Operational Efficiency Impact)

| Chỉ Số Đo Lường Nghiệp Vụ | Quy Trình Thủ Công (Chủ Shop SME) | Quy Trình Có EcomReview AI (`P1`) | Mức Cải Thiện |
| :--- | :-: | :-: | :-: |
| **Thời gian tổng hợp & phân tích 150 đánh giá** | ~90 – 120 phút | **< 2 phút** (xử lý tự động + xem Dashboard) | **Tiết kiệm ~98% thời gian** |
| **Thời gian lập kế hoạch Marketing & Vận hành** | ~45 – 60 phút (dễ bỏ sót lỗi ẩn) | **~3 – 5 phút** (duyệt `Approve/Edit` trên UI) | **Tiết kiệm ~92% thời gian** |
| **Tỷ lệ phát hiện phàn nàn ẩn trong review 4–5 sao** | < 10% (thường bị bỏ qua) | **100% (Phát hiện đủ 23/23 ca = 17.0%)** | **+90% độ phủ phát hiện** |
| **Độ chính xác số liệu thống kê & An toàn chính sách** | Cảm tính, dễ vi phạm từ khóa cam kết quá đà | **100% khớp SQL & 100% vượt qua R1–R7** | **Triệt tiêu 100% ảo giác số học** |

<!-- CreBy: MenBoyBMN -->

