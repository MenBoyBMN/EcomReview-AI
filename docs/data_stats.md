# Báo Cáo Thống Kê Khám Phá Dữ Liệu (Exploratory Data Analysis - EDA)

> **Dự án:** EcomReview AI — Nghiên cứu ABSA & Tối ưu hóa Thương mại Điện tử
> **Cập nhật:** Tuần 1 · Đã nạp dữ liệu thực tế TikTok Shop

---

## 1. Tổng Quan Cỡ Mẫu (Sample Overview)

| Phân Nhóm | Nguồn Dữ Liệu | Tổng Số Mẫu | Có Văn Bản Nhận Xét | Định Dạng Lưu Trữ |
| :--- | :--- | :--- | :--- | :--- |
| **Track 1: Public Benchmark** | VLSP / UIT-ViSFD | 3 mẫu | 3 mẫu | JSON (`data/public/`) |
| **Track 2: Shop Áo Mưa Thật** | TikTok Shop (Shop A) | 245 mẫu | 125 mẫu | CSV (`data/interim/`) |

---

## 2. Phân Bố Đánh Giá Sản Phẩm Shop Áo Mưa (Track 2)

- **Tổng số lượng đơn đánh giá:** 245 đánh giá.
- **Số lượng đánh giá có nội dung nhận xét (Text Review):** 125 mẫu (51.0%).
- **Số lượng đánh giá chỉ bấm sao (Star-only):** 120 mẫu.
- **Điểm số sao trung bình (Average Rating):** 4.66 / 5.0

### Bảng Phân Bố Theo Số Sao (Rating Breakdown):

| Số Sao | Số Lượng Đánh Giá | Tỷ Lệ (%) | Phân Loại Cảm Xúc Giả Định |
| :---: | :---: | :---: | :--- |
| 5 ⭐ | 199 | 81.2% | Tích cực (Positive) |
| 4 ⭐ | 29 | 11.8% | Tích cực / Khá |
| 3 ⭐ | 4 | 1.6% | Trung tính (Neutral) |
| 2 ⭐ | 6 | 2.4% | Tiêu cực (Negative) |
| 1 ⭐ | 7 | 2.9% | Tiêu cực nặng (Strong Negative) |

---

## 3. Đặc Trưng Văn Bản Nhận Xét (Text Statistics)

- **Độ dài trung bình:** 8.5 từ/phản hồi.
- **Độ dài ngắn nhất:** 1 từ.
- **Độ dài dài nhất:** 61 từ.
- **Hiện tượng đặc trưng trong tập dữ liệu:**
  1. Review có độ dài trung bình chứa nhiều phản hồi chi tiết về chất liệu da cá, độ mềm, và chống thấm nước.
  2. Xuất hiện các review mỉa mai ngầm và đánh giá đa khía cạnh (khen giao hàng nhưng chê dây kéo bị ngấm nước).
  3. Đã được khử khuẩn hoàn toàn số điện thoại, mã đơn hàng và email cá nhân (PII Scrubbed).

<!-- CreBy: MenBoyBMN -->
