# Biên Bản Chạy Thử Thuyết Trình Bảo Vệ Đồ Án (`Mock Defense Rehearsal Notes`)

Tài liệu này ghi nhận kết quả 2 phiên chạy thử thuyết trình bảo vệ đồ án **EcomReview AI** theo chuẩn thời lượng **12 – 15 phút** cho 18 Slides chính (kèm 6 Backup Slides dự phòng cho phần hỏi đáp).

---

## 1. Phân Bổ Thời Gian Chuẩn Cho 18 Slides Chính (`Target: 13 Phút 30 Giây`)

| Nhóm Nội Dung | Số Thứ Tự Slide | Thời Lượng Chuẩn | Điểm Nhấn Bắt Buộc Khi Trình Bày |
| :--- | :-: | :-: | :--- |
| **Phần 1: Mở đầu & Bài toán thực tế** | Slide 1 – 3 | `02:00` | Nêu rõ nỗi đau của chủ shop Áo mưa SME trên Shopee/TikTok (Teencode, Phàn nàn ẩn trong review 5 sao, Ảo giác số học của LLM thông thường) và 3 câu hỏi nghiên cứu `RQ1 – RQ3`. |
| **Phần 2: Dữ liệu & Kiến trúc hệ thống** | Slide 4 – 8 | `03:30` | Nhấn mạnh chiến lược Dữ liệu Kép ($\kappa = 0.8780$), Phòng thủ 4 lớp, SQL Aggregator có **Wilson 95% CI**, và vòng lặp `Pure Python State-Graph + HybridCritic (R1–R7) + Auto-Repair`. |
| **Phần 3: Kết quả thực nghiệm `RQ1, RQ2, RQ3`** | Slide 9 – 13 | `04:30` | Trình bày 3 bảng số liệu đắt giá: **RQ1** (`A1-v2` đạt Overall F1 = `0.8248`, $p < 0.0001$), **RQ2** (`B3` tăng `+12.05%` trên Emoji, `FIX_01` chặn 100% lỗi từ ghép), **RQ3** (`P1-Full` đạt `100%` Groundedness, thắng `10/10` chấm mù A/B với `4.98/5.0`, tỷ lệ duyệt `96.55%`). |
| **Phần 4: Phân tích lỗi Pareto & Demo thực tế** | Slide 14 – 16 | `02:30` | Chỉ vào biểu đồ Pareto (`5 nhóm lỗi đầu chiếm 80.15%`), minh họa Case Study Trước/Sau trên Shop Áo Mưa (rút ngắn thời gian từ ~2–3 giờ xuống ~5 phút). |
| **Phần 5: Kết luận & Mở rộng Local AI** | Slide 17 – 18 | `01:00` | Khẳng định hoàn thành **12/12 yêu cầu đề bài**, giới thiệu tính năng mở rộng Local AI (`Ollama + Qwen2.5-7B`) chạy miễn phí nội bộ. |

---

## 2. Nhật Ký Cải Tiến Qua 2 Lần Chạy Thử (`Rehearsal Logs`)

### Lần chạy thử 1 (`Run #1` — Tổng thời gian: `16 phút 20 giây` $\rightarrow$ Quá giờ 1 phút 20 giây)
- **Nguyên nhân:** Dành quá nhiều thời gian giải thích chi tiết từng biểu thức chính quy trong bước tiền xử lý ở Slide 5 và đọc từng dòng JSON của 10 endpoints ở Slide 8.
- **Điều chỉnh:** Chuyển chi tiết công thức toán học Wilson Score và danh sách 10 endpoints sang **Backup Slides (`B2` và `B5`)**; ở Slide chính chỉ tập trung vào sơ đồ luồng và ý nghĩa thực tiễn.

### Lần chạy thử 2 (`Run #2` — Tổng thời gian: `13 phút 25 giây` $\rightarrow$ Đạt chuẩn xuất sắc)
- **Kết quả:** Tốc độ nói vừa phải, rõ ràng, chuyển mạch mượt mà giữa 3 câu hỏi nghiên cứu `RQ1 -> RQ2 -> RQ3` và phần Demo giao diện Streamlit 4 trang; còn dư `1 phút 35 giây` dự phòng.
- **Kịch bản dự phòng khi đứng trước Hội đồng (`Fail-Safe Protocol`):**
  1. Mở sẵn `Streamlit Dashboard` (`http://localhost:8501`) ở chế độ `DEMO_CACHE_MODE=true` (phản hồi tức thì `< 80 ms`, không phụ thuộc Wi-Fi phòng bảo vệ).
  2. Mở sẵn file video `demo/EcomReview_AI_Demo.mp4` ở tab bên cạnh để có thể tua nhanh tới bất kỳ phân cảnh nào khi Hội đồng yêu cầu.

<!-- CreBy: MenBoyBMN -->
