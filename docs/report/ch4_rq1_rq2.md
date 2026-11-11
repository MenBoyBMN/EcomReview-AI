# Chương 4 (Phần 1): Kết Quả Thực Nghiệm RQ1 (So Sánh 4 Mô Hình B1, B2, B3, A1-v2) Và RQ2 (Thực Nghiệm Cắt Bỏ Chuẩn Hóa Ngôn Ngữ Mạng $4 \times 2$)

## 4.1. Giao Thức Thực Nghiệm & Đóng Băng Tập Kiểm Thử (Locked Evaluation Protocol)

Để đảm bảo tính trung thực học thuật tuyệt đối và chống hiện tượng *Data Snooping* (tinh chỉnh siêu tham số hoặc prompt trên tập test), toàn bộ quy trình thực nghiệm RQ1 và RQ2 tuân thủ cơ chế đóng băng hai tầng:
1. **Đóng băng Prompt (`analyzer-v2-frozen`):** Sau khi phân tích lỗi của A1-v1 trên tập `dev.jsonl` ($N = 60$), phiên bản prompt `prompts/analyzer_v2_frozen.md` được chốt cứng với 4 cải tiến hướng mục tiêu (phân tách ranh giới `WATERPROOF` vs `MATERIAL_DURABILITY`, quy tắc ưu tiên Mệnh đề đối lập *"Tuy... nhưng..."*, neo trích dẫn nguyên văn có độ dài $3\text{--}18$ từ, và nhận diện phàn nàn ẩn trong review 4–5 sao) và gắn thẻ Git tag `analyzer-v2-frozen`.
2. **Đóng băng Tập Test (`test_locked.jsonl`):** Tập kiểm thử miền Áo mưa (`data/gold/test_locked.jsonl`, $N = 105$ đánh giá độc lập theo sản phẩm) được kiểm tra mã băm bất biến `SHA-256 = a3956258d9611c430a18bf81f7e137822d26eb74bc28a5fcd0914acdcad76556` ở đầu script `src/ecomreview/eval/run_rq1_rq2.py`. Mọi phép đo khoảng tin cậy đều sử dụng **Cluster Bootstrap 95% CI** ($B = 1.000$ lần lấy mẫu lại ở cấp độ đơn vị `review_id`, cố định `seed = 42`).

---

## 4.2. Kết Quả Nghiên Cứu RQ1: So Sánh Hiệu Năng ABSA Đa Mô Hình (`B1`, `B2`, `B3`, `A1-v2`)

### 4.2.1. Track 1 — Đánh Giá Chéo Miền Trên Tập Benchmark Công Khai (UIT-ViSFD)
Trên tập kiểm thử công khai UIT-ViSFD (`data/public/test.jsonl`), các nhãn khía cạnh được ánh xạ về 4 nhóm vĩ mô (`MacroAspect`: `PERFORMANCE_FUNCTION`, `QUALITY_DESIGN`, `PRICE_VALUE`, `SERVICE_LOGISTICS`). Kết quả thực nghiệm (xuất từ `results/rq1_final_benchmark.csv`) được trình bày tại Bảng 4.1:

| Hệ thống / Mô hình | Overall Sentiment Macro-F1 (Bootstrap 95% CI) | Macro-Aspect Detection F1 | Độ trễ trung bình (`ms/review`) | Chi phí ước tính (`/1.000 reviews`) |
| :--- | :---: | :---: | :---: | :---: |
| **B1: Rule & Lexicon** | `0.4209 [0.3363 - 0.7333]` | `0.5558` | `2.0 ms` | `$0.00` |
| **B2: TF-IDF + Logistic Regression** | **`0.6033 [0.5500 - 0.9663]`** | **`0.6441`** | `8.3 ms` | `$0.00` |
| **B3: ViSoBERT (In-Domain Supervised)** | `0.5806 [0.5229 - 0.9395]` | `0.6397` | `11.0 ms` | `$0.00` |
| **A1-v2: Gemini Flash (Zero-Shot Cross-Domain)** | `0.5238 [0.4520 - 0.5833]` | `0.5977` | `6893.0 ms` | `$0.05` |

**Nhận xét học thuật (Track 1):** Trên miền dữ liệu điện thoại thông minh (Smartphone) nơi các mô hình có giám sát (`B2`, `B3`) được huấn luyện trực tiếp trên hàng nghìn mẫu cùng phân phối (In-Domain), `B2` và `B3` đạt hiệu năng phát hiện khía cạnh vĩ mô cao nhất (`0.6441` và `0.6397`) với độ trễ dưới `11 ms`. Trong khi đó, `A1-v2` được thiết kế chuyên biệt cho miền Áo mưa nên khi áp vào miền Điện thoại mà không chỉnh sửa prompt chỉ đạt `0.5977`.

### 4.2.2. Track 2 — Đánh Giá Thực Chiến Trên Miền Mục Tiêu Shop Áo Mưa (`test_locked.jsonl`, $N = 105$)
Khi chuyển sang bài toán thực tế của các SMEs thương mại điện tử: **phân tích 8 khía cạnh chi tiết của sản phẩm Áo mưa trong điều kiện thiếu dữ liệu gán nhãn lớn (Cross-Domain / Few-Shot Transfer)**, cục diện đảo chiều hoàn toàn (Bảng 4.2, trích xuất từ `results/rq1_final_shop.csv`):

| Hệ thống / Mô hình | Overall Sentiment F1 (95% CI) | Aspect Detection F1 | Joint ABSA Macro-F1 (95% CI) | Quote Fidelity (Độ trung thực trích dẫn) | Kiểm định Paired Bootstrap vs `A1-v2` | Độ trễ (`ms/rev`) | Chi phí (`/1k rev`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **B1: Rule & Lexicon** | `0.4187 [0.3033 - 0.5116]` | `0.8731` | `0.5680 [0.4720 - 0.6601]` | `93.5%` | $p < 0.0001$ | `0.4 ms` | `$0.00` |
| **B2: TF-IDF + LogReg** | `0.5296 [0.4485 - 0.5909]` | `0.7683` | `0.3835 [0.3532 - 0.5367]` | `100.0%` | $p < 0.0001$ | `7.1 ms` | `$0.00` |
| **B3: ViSoBERT (Cross-Domain)** | `0.5296 [0.4436 - 0.5895]` | `0.6329` | `0.3706 [0.3141 - 0.4399]` | `100.0%` | $p < 0.0001$ | `8.5 ms` | `$0.00` |
| **A1-v2: Gemini Flash (Frozen)** | **`0.8248 [0.7324 - 0.8983]`** | **`0.9066`** | **`0.6665 [0.5555 - 0.7718]`** | **`97.4%`** | **Reference** | `6300.2 ms` | `$0.05` |

**Phân tích chuyên sâu RQ1 (Track 2):**
1. **Sự vượt trội có ý nghĩa thống kê của `A1-v2`:** Mô hình đề xuất `A1-v2 (Gemini Flash Frozen)` đạt **Overall Sentiment F1 = `0.8248`**, **Aspect Detection F1 = `0.9066`** và **Joint ABSA Macro-F1 = `0.6665`**, vượt qua `B1` (`+9.85%` điểm tuyệt đối trên Joint ABSA F1 và `+40.61%` trên Overall F1), vượt xa `B2` (`+28.30%`) và `B3` (`+29.59%`). Kiểm định Paired Bootstrap xác nhận mức chênh lệch có ý nghĩa thống kê ở mức $p < 0.0001$.
2. **Hiện tượng suy giảm nghiêm trọng khi dịch chuyển miền (Domain Shift Degradation) của `B2` và `B3`:** Các mô hình học có giám sát như `B2` và `B3` bị suy giảm Joint ABSA Macro-F1 xuống dưới `0.39` trên miền Áo mưa do không nhận diện được các ngữ cảnh đặc thù ngành hàng (như *"nước ngấm qua đường ép nhiệt đũng quần"*, *"mặc trùm balo bị hớt tà sau"*, *"mùi nhựa PVC nồng"*).
3. **Độ trung thực bằng chứng (`Quote Fidelity = 97.4%`):** Nhờ cơ chế ràng buộc Pydantic Schema kết hợp hàm hậu kiểm `_post_validate_evidence`, `A1-v2` trích xuất chính xác nguyên văn câu chữ của khách hàng làm bằng chứng cho Insight Engine ở mức `97.4%` (và `100%` sau khi lọc hậu kiểm).

---

## 4.3. Kết Quả Nghiên Cứu RQ2: Thực Nghiệm Cắt Bỏ Chuẩn Hóa Ngôn Ngữ Mạng ($4 \text{ Models} \times 2 \text{ Modes}$)

Để trả lời câu hỏi nghiên cứu **RQ2**: *"Bộ chuẩn hóa ngôn ngữ mạng tiếng Việt (`normalize_social_text`: giải mã teencode, chuẩn hóa Unicode NFC, gắn nhãn cảm xúc Emoji) tác động như thế nào đến từng kiến trúc mô hình trên các lát cắt nhiễu khác nhau?"*, thực nghiệm $4 \times 2$ được tiến hành trên tập kiểm thử mở rộng có gán cờ nhiễu ($N = 145$ mẫu, bao gồm `Slice_Clean` $n=59$, `Slice_Teencode` $n=76$, `Slice_NoDiacritics` $n=9$, `Slice_Emoji` $n=12$). Bảng 4.3 tổng hợp kết quả từ `results/rq2_ablation_final.csv`:

| Hệ thống | Lát cắt dữ liệu (`Slice`) | Cỡ mẫu ($n$) | Raw ABSA F1 (`norm=OFF`) | Normalized ABSA F1 (`norm=ON`) | $\Delta \text{ABSA F1}$ | Raw Overall F1 (`norm=OFF`) | Normalized Overall F1 (`norm=ON`) | $\Delta \text{Overall F1}$ |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **B1: Rule & Lexicon** | `All_Samples` | 145 | `0.5817` | `0.5681` | `-0.0136` | `0.4673` | `0.4673` | `+0.0000` |
| **B2: TF-IDF + LogReg** | `All_Samples` | 145 | `0.6285` | `0.6250` | `-0.0035` | `0.4848` | **`0.5054`** | **`+0.0206`** |
| **B2: TF-IDF + LogReg** | `Slice_Teencode` | 76 | `0.6099` | `0.6024` | `-0.0075` | `0.5341` | **`0.5778`** | **`+0.0437`** |
| **B2: TF-IDF + LogReg** | `Slice_Emoji` | 12 | `1.0000` | `1.0000` | `+0.0000` | `0.4051` | **`0.5820`** | **`+0.1769`** |
| **B3: ViSoBERT** | `All_Samples` | 145 | `0.3896` | **`0.4059`** | **`+0.0163`** | `0.4852` | **`0.5256`** | **`+0.0404`** |
| **B3: ViSoBERT** | `Slice_Teencode` | 76 | `0.3929` | **`0.3988`** | **`+0.0059`** | `0.5300` | **`0.5662`** | **`+0.0362`** |
| **B3: ViSoBERT** | `Slice_Emoji` | 12 | `0.5458` | **`0.5868`** | **`+0.0410`** | `0.4603` | **`0.5808`** | **`+0.1205`** |
| **A1-v2: Gemini Flash** | `All_Samples` | 145 | **`0.7341`** | `0.7227` | `-0.0114` | **`0.8701`** | `0.8612` | `-0.0089` |
| **A1-v2: Gemini Flash** | `Slice_Clean` | 59 | `0.8511` | `0.8511` | `+0.0000` | `0.8522` | `0.8522` | `+0.0000` |
| **A1-v2: Gemini Flash** | `Slice_NoDiacritics` | 9 | `1.0000` | `1.0000` | `+0.0000` | `1.0000` | `1.0000` | `+0.0000` |

**Ba phát hiện khoa học trọng tâm từ RQ2:**
1. **Lợi ích rõ rệt của bộ chuẩn hóa đối với các mô hình dựa trên từ vựng / Subword (`B2` và `B3`):** Khi bật chuẩn hóa (`norm=ON`), Overall Sentiment F1 của `B3 (ViSoBERT)` tăng `+4.04%` trên toàn tập (`0.4852` $\rightarrow$ `0.5256`) và tăng vọt **`+12.05%`** trên lát cắt chứa biểu tượng cảm xúc `Slice_Emoji` (`0.4603` $\rightarrow$ `0.5808`), trong khi ABSA F1 trên `Slice_Emoji` tăng `+4.10%`. Tương tự, `B2 (TF-IDF)` tăng `+4.37%` Overall F1 trên lát cắt `Slice_Teencode` (`0.5341` $\rightarrow$ `0.5778`) và `+17.69%` trên `Slice_Emoji` nhờ việc ánh xạ các viết tắt (`ko`, `dc`, `sp`, `sz`) và emoji (`😡`, `😭`, `❤️`) về từ vựng chuẩn trong từ điển TF-IDF.
2. **Khả năng kháng nhiễu tự nhiên (Intrinsic Noise Robustness) của LLM đa ngữ (`A1-v2`):** Ngược lại với `B2`/`B3`, mô hình `A1-v2 (Gemini Flash)` đạt hiệu năng cao nhất khi đọc trực tiếp văn bản gốc (`Raw ABSA F1 = 0.7341`, `Raw Overall F1 = 0.8701`) và đạt `1.0000` tuyệt đối trên lát cắt không dấu (`Slice_NoDiacritics`).
3. **Hiện tượng "Dịch quá mức" (Over-normalization Artifact) đối với trích xuất bằng chứng của LLM:** Khi bật thay thế từ điển cứng (`norm=ON`), một số cụm từ viết tắt hoặc từ ghép (như *"chất liệu"* khi gặp chữ *"chất"* được mở rộng thành *"chất lượng liệu"*) làm biến dạng bề mặt chuỗi, khiến câu trích dẫn (`evidence`) của LLM lệch khỏi văn bản gốc (`Delta_F1 = -0.0114`). Phát hiện này dẫn tới khuyến nghị kiến trúc quan trọng cho hệ thống sản phẩm: **Sử dụng `norm=ON` cho các bộ phân loại nhẹ (`B2`, `B3`) và tìm kiếm từ khóa, nhưng truyền song song văn bản gốc `raw_text` cho `A1-v2` để bảo toàn 100% độ trung thực của bằng chứng trích dẫn (`Quote Fidelity`).**

<!-- CreBy: MenBoyBMN -->
