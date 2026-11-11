# Biên Bản Chia Tập Dữ Liệu & Khóa Mã Băm SHA-256 (Data Split & Lock Protocol)

> **Mục tiêu:** Chống rò rỉ dữ liệu và đảm bảo tính liêm chính khoa học cho ABSA.
> **Trạng thái:** Đã khóa tập kiểm thử (Test Locked) · Tuần 2

---

## 1. Kiến Trúc Dữ Liệu Kép (Dual-Track Architecture)

Hệ thống **EcomReview AI** vận hành trên 2 luồng dữ liệu độc lập:

| Luồng | Tập Dữ Liệu | Nguồn Gốc | Tổng Mẫu | Mục Đích Sử Dụng |
| :--- | :--- | :--- | :---: | :--- |
| **Track 1: Public Benchmark** | UIT-ViSFD (Normalized) | TMĐT Điện Thoại | 2.200 | Huấn luyện Baseline B2, B3 và đo chuyển miền (RQ2). |
| **Track 2: Shop Thật** | TikTok Shop Áo Mưa | Shop thực tế (Shop A) | 125 | Đánh giá thích ứng miền và chạy AI Agent (RQ1, RQ3). |

---

## 2. Chi Tiết Phân Chia Tập Dữ Liệu

### 2.1. Track 1 — Public Benchmark (`data/public/`)
- `train.jsonl`: 1.500 mẫu (dùng huấn luyện mô hình học máy và fine-tuning).
- `val.jsonl`: 300 mẫu (dùng chọn epoch và hyperparameter).
- `test.jsonl`: 400 mẫu phân tầng (dùng so sánh 4 mô hình: B1, B2, B3, A1).

### 2.2. Track 2 — Shop Áo Mưa (`data/gold/`)
- **Tập Phát Triển (`dev.jsonl` - 60 mẫu):**
  - **20 mẫu thật (`real_shop`):** Chia theo nhóm nội dung (Group-based split),
    đảm bảo không trùng lặp câu chữ với tập test.
  - **40 mẫu giả lập (`synthetic_dev`):** Gồm teencode, không dấu, emoji, mỉa mai.
  - *Mục đích:* Dùng để chọn few-shot, tinh chỉnh prompt và hiệu chỉnh ngưỡng.
- **Tập Kiểm Thử Khóa (`test_locked.jsonl` - 105 mẫu):**
  - **105 mẫu thực tế 100% từ shop áo mưa.**
  - **0% mẫu synthetic** (tuyệt đối không trộn mẫu nhân tạo vào tập test).
  - *Quy tắc:* Khóa chặt bằng SHA-256, không nhìn lỗi để sửa prompt.

---

## 3. Khóa Bảo Mật SHA-256 & Bằng Chứng Liêm Chính

| Tệp Dữ Liệu | Số Dòng | Định Dạng | Mã Băm SHA-256 |
| :--- | :---: | :---: | :--- |
| `data/gold/test_locked.jsonl` | 105 | JSONL | `a3956258d9611c430a18bf81f7e137822d26eb74bc28a5fcd0914acdcad76556` |
| `data/gold/dev.jsonl` | 60 | JSONL | `a9dacae5050988c2901bbaef44d2c4618e042b327e65f5dff43aa09013d246e4` |
| `data/public/test.jsonl` | 400 | JSONL | `536b715ea0c05c24f1af76fb6885ceb0c93981723d8927bd85c164f8f22e32df` |

### Kiểm tra rò rỉ (Leakage Audit Verification):
- Giao tập ID giữa `dev` và `test_locked`: **0 mẫu (Passed)**.
- Giao tập Text chuẩn hóa giữa `dev` và `test_locked`: **0 mẫu (Passed)**.
- Phương pháp phân chia: **Group-aware text splitting** (cố định `seed=42`).

<!-- CreBy: MenBoyBMN -->
