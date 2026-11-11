# Chương 5: Kết Luận, Đóng Góp Khoa Học – Thực Tiễn Và Hướng Phát Triển

---

## 5.1. Tổng Kết Kết Quả Nghiên Cứu Theo 3 Câu Hỏi Trọng Tâm (`RQ1 – RQ3`)

Đồ án nghiên cứu và phát triển hệ thống **EcomReview AI** đã giải quyết trọn vẹn bài toán tự động phân tích phản hồi khách hàng tiếng Việt theo khía cạnh (ABSA) và lập kế hoạch hành động marketing / cải tiến sản phẩm có căn cứ cho doanh nghiệp nhỏ và vừa (SMEs). Toàn bộ 3 câu hỏi nghiên cứu (`RQ1, RQ2, RQ3`) và 3 giả thuyết khoa học (`H1, H2, H3`) đều được kiểm chứng thực nghiệm nghiêm ngặt với khoảng tin cậy **Bootstrap 95% CI**:

1. **Trả lời `RQ1` (Hiệu năng ABSA tiếng Việt trong điều kiện Chuyển miền & Ít mẫu — Kiểm chứng giả thuyết $H_1$):**
   - Trên miền dữ liệu mục tiêu Shop Áo Mưa (`test_locked.jsonl`, $N = 105$ đánh giá thực tế khóa mã băm SHA-256, độ đồng thuận gán nhãn Cohen's Kappa $\kappa_{\text{overall}} = 0.8780$), các mô hình học có giám sát truyền thống (`B2: TF-IDF + LogReg` và `B3: ViSoBERT`) bị suy giảm nghiêm trọng do hiện tượng **Chuyển miền (`Domain Shift`)**, chỉ đạt Joint ABSA Macro-F1 lần lượt là `0.3835` và `0.3706`.
   - Ngược lại, mô hình đề xuất **`A1-v2 (Gemini Flash Frozen + Structured Output)`** đạt **Overall Sentiment F1 = `0.8248 [0.7324 - 0.8983]`**, **Aspect Detection F1 = `0.9066`** và **Joint ABSA Macro-F1 = `0.6665 [0.5555 - 0.7718]`**, vượt qua cả 3 baselines (`B1, B2, B3`) với mức ý nghĩa thống kê $p < 0.0001$ (kiểm định Paired Bootstrap) và đạt độ trung thực trích dẫn **`Quote Fidelity = 97.4%`** (`100.0%` sau hậu kiểm). Giả thuyết $H_1$ được **chấp nhận hoàn toàn**.

2. **Trả lời `RQ2` (Tác động khác biệt của Bộ chuẩn hóa ngôn ngữ mạng `normalize_social_text` — Kiểm chứng giả thuyết $H_2$):**
   - Thực nghiệm cắt bỏ $4 \times 2$ trên 145 mẫu phân tầng nhiễu chỉ ra sự phân hóa rõ rệt theo kiến trúc mô hình: Bộ chuẩn hóa giúp **`B3 (ViSoBERT)` tăng `+4.04%` Overall F1 toàn tập** (`+12.05%` trên lát cắt `Slice_Emoji`) và giúp **`B2 (TF-IDF)` tăng `+4.37%` trên `Slice_Teencode`** (`+17.69%` trên `Slice_Emoji`).
   - Trong khi đó, LLM đa ngữ `A1-v2` sở hữu khả năng kháng nhiễu tự nhiên (`F1 = 1.0000` trên văn bản không dấu `Slice_NoDiacritics`). Phát hiện về hiện tượng *Over-normalization* trên từ ghép (`"chất liệu"`) đã dẫn tới cải tiến bộ lọc ngữ cảnh `compound_followers` (`FIX_01`), triệt tiêu `100%` lỗi biến dạng từ ghép. Giả thuyết $H_2$ được **khẳng định kèm phát hiện kiến trúc mới**.

3. **Trả lời `RQ3` (Độ bám sát bằng chứng, Nhất quán số học & Khả năng áp dụng của State-Graph Agent — Kiểm chứng giả thuyết $H_3$):**
   - Tác tử một bước `P0_Single_Prompt` hoàn toàn thất bại trong việc duy trì tính xác thực số học (`Numeric Consistency = 0.00%`, `Evidence Validity = 0.00%`, `Policy & Claim Safety = 33.33%`, Điểm Critic = `1.00 / 5.0`).
   - Kiến trúc đề xuất **`P1_Full_Proposed` (kết hợp SQL/Wilson 95% CI Aggregator, `InsightEngine`, `ActionPlanner` và vòng lặp phản biện `HybridCritic` 7 quy tắc xác định `R1–R7` + `auto_repair`)** nâng `Numeric Consistency` từ `51.67%` (khi tắt Critic ở `P1_No_Critic`) lên tuyệt đối **`100.00%`**, đạt **`100.00%`** trên cả 5 chỉ số định lượng, giành chiến thắng **`100.0% (10/10 kịch bản)`** trong chấm mù A/B (Điểm Rubric tổng hợp **`4.98 / 5.00 [4.94 - 5.00]`** so với `2.17 / 5.00` của `P0`).
   - Trong quy trình duyệt nghiệp vụ thực tế và Case Study Shop Áo Mưa, tỷ lệ chấp nhận sử dụng (`Usable Adoption = APPROVED + EDITED`) đạt **`96.55%` (28/29 hành động)**, giúp rút ngắn thời gian phân tích và lập kế hoạch từ ~2–3 giờ xuống ~5 phút. Giả thuyết $H_3$ được **chứng minh thuyết phục**.

---

## 5.2. Các Đóng Góp Chính Của Đồ Án

### 5.2.1. Đóng Góp Về Mặt Học Thuật & Phương Pháp Luận
1. **Kiến trúc "Zero Numeric Hallucination" cho Tác tử Phân tích Kinh doanh:** Đề xuất mô hình kết hợp giữa **SQL Aggregator có khoảng tin cậy bất đối xứng Wilson 95% CI** và **2 chốt chặn hậu kiểm số học xác định** (`verify_numbers_in_statement` và Luật `R2`), đảm bảo mọi con số thống kê trong báo cáo của LLM đều khớp 100% với cơ sở dữ liệu gốc.
2. **Cơ chế Phản biện Lai 7 Luật Xác định (`HybridCritic` R1–R7) & Tự sửa lỗi (`Auto-Repair`):** Chứng minh rằng việc kết hợp các quy tắc kiểm chứng bằng code Python thuần với cơ chế tự sửa lỗi xác định giúp khắc phục hoàn toàn điểm yếu của LLM-as-a-Judge truyền thống (nhanh, chi phí bằng 0, bắt trúng 10/10 lỗi tiêm thử nghiệm).
3. **Bộ dữ liệu gán nhãn chất lượng cao & Phân tích lỗi Pareto `E1–E10` cho TMĐT Tiếng Việt:** Xây dựng bộ tiêu chuẩn gán nhãn 8 khía cạnh ngành Áo mưa đạt độ đồng thuận $\kappa = 0.8780$, phát hiện quy luật phàn nàn ẩn (`HIDDEN_COMPLAINT` chiếm `17.0%` trong nhóm 4–5 sao) và thiết lập bảng phân loại 10 nhóm lỗi chuẩn `E1–E10`.

### 5.2.2. Đóng Góp Về Mặt Kỹ Thuật & Sản Phẩm Thực Tiễn Cho SMEs
1. **Hệ thống Full-Stack hoàn chỉnh, bảo mật 4 lớp & Đóng gói 1-Click:** Cung cấp dịch vụ Backend FastAPI (15 RESTful Endpoints chuẩn OpenAPI 3.1), giao diện Streamlit Dashboard 5 trang trực quan hóa thanh sai số Wilson 95% CI và xu hướng theo chuỗi thời gian, hệ thống cảnh báo sớm phát hiện lỗi bằng kiểm định two-proportion z-test ($p < 0.05$), trợ lý phản hồi CSKH an toàn 6 Guardrails G1–G6, cơ sở dữ liệu 6 bảng hỗ trợ `read_only=True` isolation và đóng gói Docker Compose (`db, api, ui`) kèm chế độ `DEMO_CACHE_MODE=true` cùng bộ xuất báo cáo Excel 6 sheet / HTML in PDF.
2. **Khả năng mở rộng linh hoạt sang Local AI (`Ollama + Qwen2.5-7B`) & Tri thức miền YAML:** Tách rời hoàn toàn tri thức miền (`playbook_aomua.yaml`, `vn_social_lexicon.yaml`) và hỗ trợ chuyển đổi linh hoạt giữa Cloud API (Gemini Flash) và Local AI miễn phí chạy nội bộ (Addon 11), giúp hộ kinh doanh nhỏ vận hành với chi phí tiệm cận `$0.00`.

---

## 5.3. Hạn Chế Của Nghiên Cứu (`Limitations`)

1. **Cỡ mẫu của một số lát cắt hiếm trong tập kiểm thử miền mục tiêu:** Mặc dù tập dữ liệu tổng hợp có quy mô lớn ($N=2.200$ mẫu công khai + $245$ mẫu Shop Áo Mưa), một số lát cắt chuyên biệt như bình luận hoàn toàn không dấu (`Slice_NoDiacritics`, $n=9$) hoặc khía cạnh `CUSTOMER_SERVICE` có cỡ mẫu nhỏ, khiến khoảng tin cậy 95% CI rộng hơn các khía cạnh phổ biến.
2. **Độ trễ khi gọi trực tiếp Cloud LLM API trên lô lớn:** Khi không sử dụng bộ nhớ đệm (`cache miss`), thời gian phản hồi trung bình của `A1-v2` qua mạng là `~6.3 giây/review`. Hệ thống đã giải quyết bài toán này bằng cơ chế tác vụ ngầm bất đồng bộ (`FastAPI BackgroundTasks` trả về HTTP `202 Accepted` kèm `job_id` kiểm toán trong bảng `system_jobs_audit`).
3. **Đánh giá hiệu quả kinh doanh dài hạn (A/B Testing doanh thu thực trên sàn):** Nghiên cứu tình huống trên Shop Áo Mưa đã đo lường trực tiếp mức tiết kiệm thời gian tác nghiệp (`~95%`) và tỷ lệ chấp nhận đề xuất (`96.55%`), nhưng việc đo lường mức tăng trưởng tỷ lệ chuyển đổi (`CR%`) và giảm tỷ lệ hoàn hàng ròng trên sàn cần thời gian theo dõi kéo dài qua nhiều mùa mưa (3–6 tháng). Hệ thống đã đặt nền móng với endpoint `/api/v1/actions/{id}/impact` đo lường trước/sau can thiệp.

---

## 5.4. Hướng Phát Triển Tương Lai (`Future Work`)

1. **Mở rộng đa ngành hàng TMĐT qua Kho Playbook Mô-đun (`Multi-Domain Playbook Hub`):** Xây dựng thêm các bộ `playbook_mypham.yaml` (Mỹ phẩm), `playbook_giadung.yaml` (Đồ gia dụng) và `playbook_thoitrang.yaml` (Thời trang) để phục vụ đa dạng các nhóm nhà bán hàng SME trên Shopee, TikTok Shop và Lazada.
2. **Phân tích Đa phương thức (`Multimodal Review Analysis — Text + Image + Video`):** Tích hợp khả năng phân tích hình ảnh và video thực tế do khách hàng đính kèm trong đánh giá (ví dụ: tự động nhận diện vết rách đường ép nhiệt hoặc màu sắc thực tế của áo mưa từ ảnh feedback) bằng mô hình thị giác-ngôn ngữ.
3. **Tự động hóa Khép kín qua Shopee/TikTok Open Platform API (`Closed-Loop Execution`):** Sau khi chủ shop nhấn nút `Approve` trên trang 3 của Dashboard, hệ thống tự động đẩy nội dung phản hồi đánh giá (`REVIEW_REPLY`) hoặc cập nhật mô tả sản phẩm (`LISTING_UPDATE`) trực tiếp lên gian hàng thông qua cổng API chính thức của sàn kèm cơ chế theo dõi biến động chỉ số `CR%` theo thời gian thực.

<!-- CreBy: MenBoyBMN -->
