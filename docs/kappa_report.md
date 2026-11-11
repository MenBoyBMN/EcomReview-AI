# Báo Cáo Đo Lường Độ Tin Cậy Gán Nhãn — Intra-Annotator Cohen's Kappa (\kappa)

> **Dự án:** EcomReview AI — Nghiệm thu Tuần 3
> **Phương pháp:** Kiểm định độ đồng thuận nội bộ sau $\ge 7$ ngày trên 50 mẫu thực tế.
> **Tiêu chuẩn khoa học:** Landis & Koch (1977) — $\kappa \ge 0.75$: Xuất sắc.

---

## 1. Bảng Tổng Hợp Hệ Số Cohen's Kappa (\kappa)

| Khía Cạnh Đánh Giá | Số Lượng Mẫu | Hệ Số Cohen's Kappa (\kappa) | Mức Độ Đồng Thuận |
| :--- | :---: | :---: | :---: |
| **Overall Sentiment** | 50 | **0.8780** | Xuất sắc (Almost Perfect) |
| `Aspect.WATERPROOF` | 50 | **0.7347** | Tốt (Substantial) |
| `Aspect.MATERIAL_DURABILITY` | 50 | **0.9454** | Xuất sắc (Almost Perfect) |
| `Aspect.FIT_SIZE` | 50 | **0.8489** | Xuất sắc (Almost Perfect) |
| `Aspect.COMFORT_USABILITY` | 50 | **0.9126** | Xuất sắc (Almost Perfect) |
| `Aspect.PRICE_VALUE` | 50 | **1.0000** | Xuất sắc (Almost Perfect) |
| `Aspect.PACKAGING_SHIPPING` | 50 | **1.0000** | Xuất sắc (Almost Perfect) |
| `Aspect.CUSTOMER_SERVICE` | 50 | **1.0000** | Xuất sắc (Almost Perfect) |
| `Aspect.ACCESSIBILITY_DESIGN` | 50 | **0.9515** | Xuất sắc (Almost Perfect) |
| **TRUNG BÌNH CÁC KHÍA CẠNH** | 50 | **0.9241** | Xuất sắc (Almost Perfect) |

---

## 2. Phân Tích Các Trường Hợp Bất Đồng & Kế Hoạch Hiệu Đính

Tổng số mẫu bất đồng giữa Lượt 1 và Lượt 2: **4 / 50 mẫu**.

| Mã Đánh Giá | Nội Dung Review | Chi Tiết Bất Đồng (Lượt 1 vs Lượt 2) |
| :--- | :--- | :--- |
| `tts_0109` | Áo có độ dày vừa phải mặt tốt ít bị thấm mưa | WATERPROOF: R1=none vs R2=positive<br>FIT_SIZE: R1=positive vs R2=none |
| `tts_0144` | Đặc điểm: Cố áo còn hơ chưa mặc cảm thấy nó vô nước từ cổ áo | Overall: R1=positive vs R2=negative<br>WATERPROOF: R1=none vs R2=negative<br>COMFORT_USABILITY: R1=negative vs R2=none |
| `tts_0196` | Chưa biết có bền k | Overall: R1=positive vs R2=neutral<br>MATERIAL_DURABILITY: R1=positive vs R2=neutral |
| `tts_0078` | đúng ảnh | Overall: R1=positive vs R2=neutral<br>ACCESSIBILITY_DESIGN: R1=positive vs R2=none |

---

## 3. Phân Tích Nguyên Nhân Bất Đồng & Đóng Góp Của Quy Trình Hiệu Đính

Độ đồng thuận trung bình giữa 2 lượt gán nhãn độc lập đạt **$\kappa_{\text{mean}} = 0.9241$** (Overall Sentiment $\kappa = 0.8780$, vượt ngưỡng chuẩn khoa học $\kappa \ge 0.75$). Phân tích 4 ca bất đồng chỉ ra các trường hợp biên đã được hiệu đính:

1. **Đa nghĩa của từ ngữ trong ngữ cảnh:** Các cụm như 'độ dày vừa phải' hay 'vừa túi tiền' dễ tạo giao thoa giữa `FIT_SIZE`, `MATERIAL_DURABILITY` và `PRICE_VALUE`.
2. **Khía cạnh ẩn & Phủ định kép:** Các câu nhận xét kiểu 'ít bị thấm mưa', 'mưa không thấm' được rà soát kỹ để gán chuẩn `WATERPROOF: positive`.
3. **Mâu thuẫn giữa Rating và Nội dung (Hidden Complaint):** Mẫu `tts_0144` khách chấm 5 sao nhưng chê 'vô nước từ cổ áo' được thống nhất gán `WATERPROOF: negative`.
4. **Phân định câu cụt ngủn ('Ok', '✅', 'Hàng chất lượng'):** Được chuẩn hóa tiêu chí `informative = False` và gán nhãn `GENERAL` theo đúng `annotation_guideline.md`.

---

## 4. Kết Luận Khoa Học & Ý Nghĩa Đối Với Hội Đồng
1. **Độ tin cậy cao ($\kappa \ge 0.75$):** Chứng minh bộ quy tắc `annotation_guideline.md` có ranh giới ngữ nghĩa rõ ràng, nhất quán qua thời gian ($\ge 7$ ngày).
2. **Nâng chuẩn dữ liệu vàng (`gold_v2.jsonl`):** Toàn bộ các ca bất đồng được rà soát và hợp nhất sang `data/gold/gold_v2.jsonl` (125 mẫu) phục vụ Tuần 4.

<!-- CreBy: MenBoyBMN -->
