# Báo Cáo Thống Kê Khám Phá Dữ Liệu (Exploratory Data Analysis - EDA)

> **Cập nhật lần cuối:** Tuần 1
> **Trạng thái:** Track 1 (Public Benchmark) + Track 2 (Shop Áo Mưa)

---

## 1. Tổng Quan Cỡ Mẫu (Sample Overview)

| Tập Dữ Liệu | Nguồn | Số Mẫu | Định Dạng | Trạng Thái PII |
| :--- | :--- | :--- | :--- | :--- |
| **Track 1: Public Benchmark** | VLSP / UIT-ViSFD | 3 mẫu | JSON (`data/public/`) | Công khai, không có PII |
| **Track 2: Shop Áo Mưa** | Shopee / TikTok Shop | 0 mẫu | CSV (`data/interim/`) | Đã khử khuẩn PII bằng Regex |

---

## 2. Đặc Trưng Dữ Liệu Shop Áo Mưa (Track 2)

- **Tổng số mẫu:** 0 phản hồi.
- **Độ dài trung bình (số từ):** 0.0 từ/phản hồi.
- **Phân bố số sao (Rating):**
  - Số lượng mẫu có rating: 0
  - Điểm rating trung bình: 0.00 / 5.0

> [!NOTE]
> Khi bạn bổ sung thêm dữ liệu vào `data/raw/shop_reviews_raw.csv`, hãy chạy lại script `python scripts/anonymize_shop_data.py` và `python scripts/eda_week1.py` để cập nhật bảng thống kê tự động.

<!-- CreBy: MenBoyBMN -->
