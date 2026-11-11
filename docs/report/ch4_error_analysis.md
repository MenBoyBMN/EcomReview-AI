# Chương 4 (Phần 3): Phân Tích Lỗi Hệ Thống Theo Quy Luật Pareto (`E1–E10`), Cải Tiến Hậu Kiểm & Các Đe Dọa Đến Giá Trị Nghiên Cứu (`Threats to Validity`)

---

## 4.7. Phân Tích Lỗi Có Hệ Thống (`Systematic Error Taxonomy E1–E10`) Và Biểu Đồ Pareto

Để hiểu rõ giới hạn của từng kiến trúc mô hình và nguyên nhân gốc rễ của các ca thất bại từ tầng NLP (RQ1, RQ2) đến tầng Agent (RQ3), toàn bộ **136 ca lỗi** phát sinh trong quá trình thực nghiệm được phân loại vào **10 nhóm lỗi chuẩn (`E1 – E10`)** tại `results/error_taxonomy.csv` và trực quan hóa trên biểu đồ Pareto (`docs/report/figures/error_pareto.png`):

| Hạng | Mã Lỗi | Nhóm Lỗi Hệ Thống (`Error Category`) | Tầng Kiến Trúc | Số Lỗi ($N=136$) | Tỷ Trọng (`%`) | Tích Lũy (`%`) | Biện Pháp Khắc Phục Trong Hệ Thống |
| :-: | :-: | :--- | :--- | :-: | :-: | :-: | :--- |
| 1 | **`E6`** | Suy giảm do Chuyển miền (`Domain Shift Degradation`) | NLP (`B2`, `B3`) | `38` | `27.94%` | `27.94%` | Chuyển sang `A1-v2` (Gemini Flash) có nhúng tri thức miền Áo mưa. |
| 2 | **`E1`** | Nhầm ranh giới khía cạnh (`Aspect Boundary Confusion`) | NLP (`B1–B3`, `A1-v1`) | `24` | `17.65%` | `45.59%` | Quy tắc ưu tiên hệ quả (`Consequence-first`) trong `analyzer_v2_frozen.md`. |
| 3 | **`E2`** | Đảo cực câu ghép đối lập & Phàn nàn ẩn (`Contrastive Inversion`) | NLP (`B1–B3`) | `19` | `13.97%` | `59.56%` | Ưu tiên mệnh đề sau *"nhưng"* + bộ dò `HIDDEN_COMPLAINT` trong `InsightEngine`. |
| 4 | **`E8`** | Ảo giác số học & Lệch chỉ mục Insight trước Critic | Agent (`P0`, `P1-Vòng 0`) | `16` | `11.76%` | `71.32%` | Hàm `verify_numbers_in_statement` + Luật **R2** & `auto_repair` trong `HybridCritic`. |
| 5 | **`E4`** | Dịch quá mức từ ghép Teencode (`Over-Normalization`) | Tiền xử lý (`normalize.py`) | `12` | `8.82%` | **`80.15%`** | Bổ sung `compound_followers` lookahead guard cho từ `"chất"` và `"chat"`. |
| 6 | **`E3`** | Bỏ sót khía cạnh phụ trong câu dài (`Multi-Aspect Omission`) | NLP (`B2`, `B3`, `A1-v2`) | `9` | `6.62%` | `86.76%` | Quét phân đoạn theo dấu phẩy và liên từ trong prompt phân tích. |
| 7 | **`E7`** | Cam kết quá đà & Vi phạm chính sách sàn ở `P0` | Agent Safety (`P0`) | `8` | `5.88%` | `92.65%` | Chặn 100% bằng Luật **R4 (`No Overclaiming`)** và **R7 (`Policy Safety`)**. |
| 8 | **`E5`** | Biến đổi nhẹ câu chữ khi trích dẫn (`Evidence Paraphrasing`) | Evidence (`B1`, `A1`) | `5` | `3.68%` | `96.32%` | Hậu kiểm chuỗi con nguyên văn `_post_validate_evidence`. |
| 9 | **`E9`** | Sinh hành động chung ở khía cạnh `GENERAL` | Agent (`HybridCritic`) | `3` | `2.21%` | `98.53%` | Xếp hạng ưu tiên `compute_priority_score` đẩy các khía cạnh cụ thể lên đầu. |
| 10 | **`E10`** | Độ trễ mạng & Giới hạn tần suất Cloud API (`Rate Limit`) | Hạ tầng (`Cloud API`) | `2` | `1.47%` | `100.00%` | Cơ chế Cache SHA-256 (`DEMO_CACHE_MODE=true`) & Local AI Ollama (Addon 11). |

**Ba kết luận rút ra từ phân tích lỗi Pareto & cải tiến hậu kiểm (`results/post_hoc_fixes.csv`):**
1. **Quy luật Pareto 80/20 thể hiện rõ nét:** 5 nhóm lỗi đứng đầu (`E6, E1, E2, E8, E4`) chiếm chính xác **`80.15%` (109/136 ca lỗi)**. Trong đó, riêng lỗi dịch chuyển miền `E6` ở các mô hình học có giám sát truyền thống (`B2`, `B3`) và nhầm ranh giới khía cạnh `E1` đã chiếm gần một nửa tổng số lỗi (`45.59%`).
2. **Hiệu quả của cải tiến hậu kiểm đối với lỗi `E4` (`FIX_01` trong `normalize.py`):** Bằng cách bổ sung bộ lọc ngữ cảnh theo sau (`compound_followers` lookahead guard), hàm `normalize_social_text` đã khắc phục triệt để hiện tượng biến `"chất liệu"` thành `"chất lượng liệu"` hoặc `"chat với shop"` thành `"chất lượng với shop"`, đạt **0% biến dạng từ ghép** trên toàn bộ tập kiểm thử hồi quy (`tests/test_regression.py`).
3. **Khả năng tự phục hồi 100% ở tầng Agent (`FIX_02`):** Mặc dù ở vòng khởi tạo đầu tiên (`Iteration 0`), tác tử có thể gặp lỗi `E8` (tham chiếu chéo lệch chỉ mục số liệu giữa các Insights), chốt chặn `HybridCritic` R1–R7 và `auto_repair` đã phát hiện và sửa chữa 100% trước khi xuất bản tới người dùng.

---

## 4.8. Các Đe Dọa Đến Giá Trị Nghiên Cứu (`Threats to Validity`)

Để đảm bảo tính khách quan khoa học, nghiên cứu ghi nhận rõ 3 nhóm hạn chế và biện pháp giảm thiểu tương ứng:
1. **Giá trị Nội tại (`Internal Validity`):**
   - *Rủi ro:* Hiện tượng rò rỉ dữ liệu (*Data Leakage*) giữa tập tinh chỉnh prompt (`dev.jsonl`) và tập kiểm thử cuối cùng (`test_locked.jsonl`), hoặc sai số khi cỡ mẫu của một số khía cạnh nhỏ.
   - *Biện pháp giảm thiểu:* Chia tách dữ liệu theo cụm văn bản (`Group-aware split`, `seed=42`), khóa mã băm `SHA-256` cho `test_locked.jsonl` ($N=105$), áp dụng ngưỡng mẫu tối thiểu $n \ge 5$ cùng khoảng tin cậy bất đối xứng **Wilson 95% CI** trong SQL Aggregator.
2. **Giá trị Ngoại tại (`External Validity`):**
   - *Rủi ro:* Tập dữ liệu thực tế `real_shop` tập trung sâu vào ngành hàng **Áo mưa thời trang & tiện lợi** trên Shopee và TikTok Shop, có thể cần điều chỉnh từ vựng khi chuyển sang ngành hàng khác (như Mỹ phẩm, Đồ gia dụng điện tử).
   - *Biện pháp giảm thiểu:* Kiến trúc hệ thống tách bạch hoàn toàn giữa **Engine xử lý (`src/ecomreview/`)** và **Tri thức miền cấu hình ngoài (`knowledge/playbook_aomua.yaml`, `knowledge/vn_social_lexicon.yaml`)**. Khi áp dụng cho ngành hàng mới, doanh nghiệp chỉ cần thay thế file YAML mà không cần viết lại mã nguồn State-Graph hay SQL Aggregator.
3. **Giá trị Khái niệm (`Construct Validity`):**
   - *Rủi ro:* Đánh giá chất lượng kế hoạch hành động marketing có thể chịu ảnh hưởng chủ quan nếu chỉ chấm điểm cảm tính.
   - *Biện pháp giảm thiểu:* Áp dụng **Khung Đánh giá Tam giác (`Triangulated Evaluation`)** kết hợp: (i) 5 chỉ số định lượng tự động bằng code (`groundedness.py`), (ii) Chấm mù A/B ẩn danh theo Rubric 5 tiêu chí `C1–C5` có kiểm định Bootstrap 95% CI, và (iii) Đo lường tỷ lệ chấp nhận sử dụng (`Usable Adoption = 96.55%`) kèm khoảng cách chỉnh sửa ký tự (`edit_distance_chars`).

<!-- CreBy: MenBoyBMN -->

