# Phân Tích Lỗi Hệ Thống (Systematic Error Analysis — Pareto E1–E10) & Cải Tiến Hậu Kiểm (`Post-Hoc Fixes`)

Tài liệu này phân tích toàn diện **136 ca lỗi** được thu thập xuyên suốt hai tầng của hệ thống **EcomReview AI**: tầng phân tích ngữ nghĩa theo khía cạnh (**NLP / ABSA — RQ1 & RQ2**) và tầng lập kế hoạch hành động của tác tử (**Agentic Planning & Critic Traces — RQ3**).

---

## 1. Bảng Phân Loại 10 Nhóm Lỗi Chuẩn (`Error Taxonomy E1–E10` & Phân Bố Pareto)

Dữ liệu trích xuất từ `results/error_taxonomy.csv` và trực quan hóa tại biểu đồ `docs/report/figures/error_pareto.png`:

| Hạng Pareto | Mã Lỗi | Tên Nhóm Lỗi (`Error Category`) | Tầng Hệ Thống | Số Ca Lỗi ($n=136$) | Tỷ Trọng (`%`) | Tích Lũy Pareto (`%`) | Nhóm 80/20 (`Vital Few`) |
| :-: | :-: | :--- | :--- | :-: | :-: | :-: | :-: |
| 1 | **`E6`** | Suy giảm hiệu năng do Chuyển miền (`Domain Shift Degradation`) | NLP (`B2`, `B3`) | `38` | `27.94%` | `27.94%` | **YES** |
| 2 | **`E1`** | Nhầm lẫn ranh giới khía cạnh (`Aspect Boundary Confusion`) | NLP (`B1–B3`, `A1-v1`) | `24` | `17.65%` | `45.59%` | **YES** |
| 3 | **`E2`** | Đảo cực do câu ghép đối lập & Phàn nàn ẩn (`Contrastive & Implicit Negativity`) | NLP (`B1–B3`) | `19` | `13.97%` | `59.56%` | **YES** |
| 4 | **`E8`** | Ảo giác số học & Lệch chỉ mục Insight trước Critic (`Pre-Critic Numeric Mismatch`) | Agent (`P0`, `P1-Vòng 0`) | `16` | `11.76%` | `71.32%` | **YES** |
| 5 | **`E4`** | Dịch quá mức từ ghép Teencode & Từ đa nghĩa (`Over-Normalization & Polysemy`) | Tiền xử lý (`normalize.py`) | `12` | `8.82%` | **`80.15%`** | **YES** |
| 6 | **`E3`** | Bỏ sót khía cạnh phụ trong câu dài đa ý (`Multi-Aspect Omission`) | NLP (`B2`, `B3`, `A1-v2`) | `9` | `6.62%` | `86.76%` | NO |
| 7 | **`E7`** | Cam kết quá đà & Vi phạm chính sách sàn ở `P0` (`Overclaiming & Policy Violation`) | Agent Safety (`P0`) | `8` | `5.88%` | `92.65%` | NO |
| 8 | **`E5`** | Biến đổi nhẹ câu chữ khi trích dẫn bằng chứng (`Evidence Paraphrasing`) | Evidence (`B1`, `A1`) | `5` | `3.68%` | `96.32%` | NO |
| 9 | **`E9`** | Critic bắt chặt hoặc sinh hành động chung ở `GENERAL` (`Generic Aspect Action`) | Agent (`HybridCritic`) | `3` | `2.21%` | `98.53%` | NO |
| 10 | **`E10`** | Độ trễ mạng & Giới hạn tần suất gọi Cloud API (`API Latency & Rate Limit`) | Hạ tầng (`Cloud API`) | `2` | `1.47%` | `100.00%` | NO |

> **Quy luật Pareto 80/20:** Đúng **5 nhóm lỗi đầu tiên (`E6, E1, E2, E8, E4`)** chiếm tới **`80.15%` (109 / 136 ca lỗi)** của toàn bộ các hệ thống được thử nghiệm.

---

## 2. Phân Tích Chuyên Sâu 8 Ca Lỗi Điển Hình (`Qualitative Case Analysis`)

1. **Ca lỗi #1 (`E6` — Domain Shift trên `tts_0053`):**
   - **Văn bản gốc:** *"Đi mưa to nước ngấm qua đường may đáy quần ướt hết cả trong."*
   - **Hiện tượng:** `B2 (TF-IDF)` và `B3 (ViSoBERT)` được huấn luyện trên tập Smartphone (UIT-ViSFD) không có trọng số cho cụm *"ngấm qua đường may đáy quần"*, dẫn đến bỏ sót nhãn `WATERPROOF#negative`. Trong khi đó, `A1-v2 (Gemini Flash)` nhận diện chính xác 100%.
2. **Ca lỗi #2 (`E1` — Nhầm ranh giới `WATERPROOF` vs `MATERIAL_DURABILITY` trên `tts_0024`):**
   - **Văn bản gốc:** *"Đường may ép nhiệt không kỹ nên đi mưa lớn bị rỉ nước vào ngực."*
   - **Hiện tượng:** Ở phiên bản `A1-v1`, mô hình chỉ gán nhãn `MATERIAL_DURABILITY` do thấy từ *"đường may"*. Sau khi bổ sung **Quy tắc ưu tiên hệ quả (Consequence-first Rule)** trong `analyzer_v2_frozen.md`, `A1-v2` gán đúng đồng thời cả `WATERPROOF#negative` và `MATERIAL_DURABILITY#negative`.
3. **Ca lỗi #3 (`E2` — Câu ghép đối lập 5 sao chứa phàn nàn ẩn trên `dev_syn_0003`):**
   - **Văn bản gốc:** *"Shop giao hàng siêu nhanh cho 5 sao nhưng vải áo hơi mỏng và nồng mùi nhựa."* (Rating = 5 sao).
   - **Hiện tượng:** `B1` và `B2` bị từ khóa tích cực *"siêu nhanh"*, *"5 sao"* ở vế đầu kéo lệch `overall_sentiment` sang `positive`. Module `HIDDEN_COMPLAINT` trong `InsightEngine` kết hợp `A1-v2` đã bắt trọn vẹn nhóm lỗi này (`23/135` đánh giá 4–5 sao).
4. **Ca lỗi #4 (`E4` — Over-normalization từ ghép `"chất liệu"` trên `tts_0052`):**
   - **Văn bản gốc:** *"Chất liệu vải dù dày dặn nhưng chat với shop hơi chậm."*
   - **Hiện tượng:** Luật thay thế từ đơn `"chất" -> "chất lượng"` và `"chat" -> "chất lượng"` trong `TEENCODE_MAP` biến câu trên thành *"chất lượng liệu vải dù dày dặn nhưng chất lượng với shop hơi chậm"*, làm mất từ khóa `"chất liệu"` của `B1` và làm sai lệch ngữ nghĩa vế sau.
5. **Ca lỗi #5 (`E8` — Ảo giác số học ở `P0` và lệch chỉ mục ở `P1-No-Critic` tại kịch bản `S1`):**
   - **Hiện tượng:** `P0` tự bịa *"Khoảng 85% khách hàng phàn nàn thấm nước"* (trong khi SQL thực tế là `14/18 = 77.8%`). Ở `P1-No-Critic` (Vòng 0), hành động số 2 lấy câu lý giải từ Insight #2 nhưng gán `insight_ids=[1]`. Bộ `HybridCritic` (Luật **R2**) đã bắt 100% và tự động sửa qua `auto_repair`.
6. **Ca lỗi #6 (`E7` — Cam kết quá đà & Vi phạm chính sách sàn ở `P0` tại kịch bản `S1` & `S7`):**
   - **Hiện tượng:** `P0` đề xuất cập nhật tiêu đề *"Cam kết chống thấm 100% tuyệt đối"* và gợi ý *"Hoàn tiền 20k qua ví ngoài nếu khách sửa đánh giá 1 sao thành 5 sao"*. Cả hai vi phạm nghiêm trọng này đều bị Luật **R4** và **R7** của `HybridCritic` chặn đứng hoàn toàn.
7. **Ca lỗi #7 (`E3` — Bỏ sót khía cạnh phụ trong câu ghép 4 ý trên `tts_0179`):**
   - **Văn bản gốc:** *"Màu xanh rêu đẹp, giao nhanh, túi đựng hơi rách nhẹ, giá 150k cũng tạm ổn."*
   - **Hiện tượng:** Các mô hình baseline thường chỉ bắt được `ACCESSIBILITY_DESIGN` và `PACKAGING_SHIPPING` mà bỏ sót `PRICE_VALUE#neutral`.
8. **Ca lỗi #8 (`E5` — Chuẩn hóa câu chữ trong trích dẫn bằng chứng trên `tts_0096`):**
   - **Hiện tượng:** Khi khách viết tắt *"áo đi mưa to bị thấm nc"*, LLM đôi khi trả về `evidence = "áo đi mưa to bị thấm nước"`. Hàm `_post_validate_evidence` trong `a1_gemini.py` đã giải quyết triệt để bằng cách đối chiếu trên cả `raw_text` và `norm_text` và khôi phục chuỗi con nguyên văn.

---

## 3. Kết Quả Cải Tiến Hậu Kiểm (`Post-Hoc Fixes` Trên Tập `dev.jsonl` — Task 9.2)

Tuân thủ kỷ luật nghiên cứu (tuyệt đối không chạm vào kết quả `test_locked.jsonl` đã đóng băng ở Tuần 4), 3 cải tiến hậu kiểm (`FIX_01`, `FIX_02`, `FIX_03` lưu tại `results/post_hoc_fixes.csv`) được kiểm chứng trên tập `dev.jsonl` và kiểm thử hồi quy `tests/test_regression.py`:

| Mã Fix | Nhóm Lỗi Mục Tiêu | Thành Phần Can Thiệp | Trước Khi Sửa (`Before`) | Sau Khi Sửa (`After`) |
| :-: | :-: | :--- | :--- | :--- |
| **`FIX_01`** | `E4 / E5` | `src/ecomreview/normalize.py` (`compound_followers` lookahead guard) | `100%` cụm *"chất liệu / chất vải / chat với shop"* bị biến dạng thành *"chất lượng liệu / chất lượng với shop"*. | **`0%` biến dạng từ ghép**; giữ nguyên `"chất liệu"`, `"chất vải"`, `"chat với shop"` trong khi vẫn chuẩn hóa đúng `"áo cực chất!" -> "áo cực chất lượng!"`. |
| **`FIX_02`** | `E8` | `src/ecomreview/agent/critic.py` (`R2` & `auto_repair`) | `Numeric Consistency = 51.67%` khi tắt Critic (`P1-No-Critic` Vòng 0). | **`Numeric Consistency = 100.00%`** (`+48.33%` sau khi kích hoạt `HybridCritic` R2 & `auto_repair`). |
| **`FIX_03`** | `E1 / E2` | `prompts/analyzer_v2_frozen.md` (Consequence-first & Contrastive Rule) | `A1-v1` đạt Macro-F1 = `0.8603` trên `dev.jsonl` (nhầm 4 ca đường may thấm nước). | **`A1-v2` đạt Macro-F1 = `0.9120`** (`+5.17%` trên tập `dev.jsonl`). |

<!-- CreBy: MenBoyBMN -->
