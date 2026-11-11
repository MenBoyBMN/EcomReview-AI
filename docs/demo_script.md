# Kịch Bản Quay Dựng Video Demo Hệ Thống EcomReview AI (Thời Lượng: 6 Phút 30 Giây — 7 Phân Cảnh)

Tài liệu này là kịch bản thuyết trình chi tiết (chia thành **7 phân cảnh**) phục vụ:
1. Kết xuất tự động video demo Full HD 1080p (`demo/EcomReview_AI_Demo.mp4`) thông qua script `scripts/generate_demo_video.py`.
2. Hướng dẫn chi tiết từng bước nếu bạn muốn tự thu âm giọng đọc cá nhân kèm quay màn hình bằng phần mềm **OBS Studio**.

---

## 1. Bảng Phân Cảnh & Lời Bình Thuyết Minh (`7-Scene Storyboard`)

| Cảnh | Thời Lượng | Nội Dung Hiển Thị Trên Màn Hình | Lời Bình / Phụ Đề Tiếng Việt (`Narration`) |
| :-: | :-: | :--- | :--- |
| **Cảnh 1** | `00:00 – 00:45` *(45s)* | Slide mở đầu & Bài toán thực tế của các chủ shop Áo mưa trên Shopee / TikTok Shop. | *"Xin chào Hội đồng chấm đồ án. EcomReview AI giải quyết bài toán tự động phân tích phản hồi khách hàng tiếng Việt theo 8 khía cạnh ngành Áo mưa và lập kế hoạch hành động Marketing / Vận hành có căn cứ xác thực tuyệt đối cho doanh nghiệp nhỏ (SMEs)."* |
| **Cảnh 2** | `00:45 – 01:40` *(55s)* | Kiến trúc 3 tầng (`FastAPI + Streamlit + PostgreSQL/SQLite`), Phòng thủ 4 lớp và Đồ thị trạng thái `State-Graph + HybridCritic R1–R7`. | *"Điểm đột phá của hệ thống là kiến trúc Zero Numeric Hallucination: 100% số liệu và khoảng tin cậy bất đối xứng Wilson 95% CI được tính bằng SQL trước khi đưa vào InsightEngine, kết hợp vòng lặp phản biện HybridCritic kiểm tra 7 quy tắc xác định R1 đến R7."* |
| **Cảnh 3** | `01:40 – 02:40` *(60s)* | **Trang 1 Dashboard (`Tổng Quan & Wilson 95% CI`):** Chọn kịch bản `real_shop` (150 đánh giá), xem biểu đồ Plotly có thanh sai số bất đối xứng và 7 Insights tự động. | *"Trên Trang 1 của Streamlit Dashboard, hệ thống hiển thị trực quan tỷ lệ tiêu cực kèm thanh sai số Wilson 95% CI. Đặc biệt, hệ thống phát hiện tự động 23 phàn nàn ẩn (17.0%) nằm trong nhóm đánh giá 4–5 sao và chênh lệch 47.3% giữa Shopee và TikTok Shop."* |
| **Cảnh 4** | `02:40 – 03:35` *(55s)* | **Trang 2 Dashboard (`Khám Phá Đánh Giá & Bằng Chứng`):** Lọc khía cạnh `WATERPROOF`, xem các mã review thực tế (`tts_0053`, `tts_0024`) và câu trích dẫn nguyên văn đã ẩn danh PII. | *"Tại Trang 2, chủ shop có thể kiểm tra từng câu trích dẫn bằng chứng nguyên văn đã được che giấu số điện thoại PII và lọc trùng lặp Jaccard <= 0.70, đảm bảo tính minh bạch và truy vết 100%."* |
| **Cảnh 5** | `03:35 – 04:40` *(65s)* | **Trang 3 Dashboard (`Kế Hoạch Hành Động & Phê Duyệt HITL`):** Xem tách biệt tab Marketing (`is_marketing=True`) và Vận hành (`is_marketing=False`), thao tác `Approve / Edit / Reject`. | *"Tại Trang 3, mỗi đề xuất hành động đều hiển thị rõ 4 thành phần What, Why, How/When có thời hạn cụ thể và KPI, gắn kèm tối thiểu 2 mã review thật. Chủ shop thực hiện phê duyệt Approve hoặc chỉnh sửa nhẹ Edit với khoảng cách ký tự được ghi nhận vào bảng kiểm toán."* |
| **Cảnh 6** | `04:40 – 05:35` *(55s)* | **Trang 4 Dashboard (`Nạp Dữ Liệu & Trace Kiểm Định`) + FastAPI Swagger `/docs`:** Nạp đánh giá mới, xem nhật ký `HybridCritic` bắt lỗi R2 và tự sửa qua `auto_repair`. | *"Tại Trang 4 và giao diện OpenAPI 3.1 gồm 10 endpoints, ta quan sát trực tiếp vết thực thi Trace JSON: khi vòng khởi tạo có lệch chỉ mục số liệu R2, HybridCritic lập tức phát hiện và kích hoạt Auto-Repair đạt điểm tuyệt đối 5.0/5.0."* |
| **Cảnh 7** | `05:35 – 06:30` *(55s)* | Tổng kết kết quả thực nghiệm `RQ1, RQ2, RQ3`, biểu đồ Pareto `E1–E10` và khả năng chạy Offline Cache / Local AI Ollama `Qwen2.5-7B`. | *"Tổng kết thực nghiệm: A1-v2 đạt Overall F1 = 0.8248 (p < 0.0001); P1-Full đạt 100% trên cả 5 chỉ số Groundedness/Safety, thắng 10/10 kịch bản chấm mù A/B (4.98/5.0) và đạt tỷ lệ chấp nhận 96.55%, tiết kiệm 95% thời gian cho chủ shop SME."* |

---

## 2. Hướng Dẫn Tự Thu Âm Thêm Bằng OBS Studio (Tùy Chọn Dành Cho Bạn)

Nếu bạn muốn tự quay màn hình kèm giọng nói cá nhân của mình (ngoài file video `demo/EcomReview_AI_Demo.mp4` đã được tạo sẵn trong repo):
1. Mở 2 cửa sổ Terminal và chạy:
   - Terminal 1: `.venv\Scripts\python.exe -m uvicorn ecomreview.api.main:app --port 8000`
   - Terminal 2: `.venv\Scripts\python.exe -m streamlit run src/ecomreview/ui/app.py --server.port 8501`
2. Mở trình duyệt ở chế độ toàn màn hình (`F11`) tại `http://localhost:8501` và `http://localhost:8000/docs`.
3. Mở **OBS Studio** $\rightarrow$ Chọn `Display Capture (1920x1080, 30fps)` + `Audio Input Capture` $\rightarrow$ Nhấn **Start Recording** và đọc theo đúng 7 lời bình trong bảng trên.

<!-- CreBy: MenBoyBMN -->
