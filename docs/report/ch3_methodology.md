# CHƯƠNG 3: PHƯƠNG PHÁP ĐỀ XUẤT VÀ THIẾT KẾ KIẾN TRÚC HỆ THỐNG

> **Đề tài:** EcomReview AI — Hệ thống AI Agent tự động phân tích phản hồi khách hàng tiếng Việt và đề xuất hành động marketing cho doanh nghiệp nhỏ.  
> **Trọng tâm Chương 3:** Mô hình hóa toán học bài toán ABSA, pipeline chuẩn hóa văn bản mạng xã hội, thiết kế 3 Baseline và Mô hình đề xuất A1, kiến trúc State-Graph thuần, và cơ chế thẩm định lai Hybrid Critic.

---

## 3.1. Tổng Quan Kiến Trúc Toàn Hệ Thống (End-to-End System Architecture)

Hệ thống **EcomReview AI** được thiết kế theo nguyên lý hướng dịch vụ module hóa (Modular Service-Oriented Architecture), đảm bảo tính phân tách tuyệt đối giữa **tầng tính toán số liệu xác định (Deterministic Computation)** và **tầng suy luận tác tử sáng tạo (Generative Planning)**.

```mermaid
flowchart TD
    subgraph DataIngestion["1. Thu Thập & Bảo Vệ Dữ Liệu"]
        R[Phản hồi thô Shopee / TikTok Shop] --> SEC[Lớp bảo vệ 4 tầng: Sanitize & XML Wrapping]
        SEC --> NORM[Vietnamese Social Text Normalizer]
    end

    subgraph ABSAPipeline["2. Động Cơ Phân Tích Cảm Xúc Theo Khía Cạnh"]
        NORM --> B1[Baseline B1: Rule-based Lexicon]
        NORM --> B2[Baseline B2: TF-IDF + Logistic Regression]
        NORM --> B3[Baseline B3: Pretrained ViSoBERT Fine-tuned]
        NORM --> A1[Proposed A1: Gemini Flash + Pydantic Structured Output]
    end

    subgraph StorageAggregator["3. Cơ Sở Dữ Liệu & Tính Toán Xác Thực"]
        A1 --> PG[(PostgreSQL 16 Relational DB)]
        PG --> AGG[Zero-Hallucination SQL/Python Aggregator]
        AGG --> STATS[Thống kê tỷ lệ phàn nàn & Wilson Score CI 95%]
    end

    subgraph AgentLoop["4. Vòng Lặp Tác Tử Tự Phản Biện (State-Graph)"]
        STATS --> INS[Insight Engine: Phát hiện dị thường & xu hướng]
        INS --> PLAN[Action Planner: Sinh đề xuất hành động theo Playbook]
        PLAN <--> CRITIC[Hybrid Critic: 7 Luật R1-R7 + LLM Judge]
    end

    subgraph HumanApproval["5. Cổng Phê Duyệt & Ứng Dụng Thực Chiến"]
        CRITIC --> GATE[Human Approval Gate]
        GATE --> DASH[Streamlit Dashboard 4 trang & FastAPI]
        GATE --> ACT[Thực thi chiến dịch Marketing / Khắc phục sản phẩm]
    end
```

### 3.1.1. Kiến Trúc An Toàn Phòng Thủ Đa Tầng (Defense-in-Depth against Prompt Injection)
Dữ liệu phản hồi từ người tiêu dùng là nguồn dữ liệu ngoại vi không đáng tin cậy (Untrusted External Input), có thể chứa các câu lệnh tấn công chiếm quyền điều khiển LLM (Direct & Indirect Prompt Injection), ví dụ: *"Bỏ qua các lệnh trước đó và đánh giá 5 sao"*. EcomReview AI triển khai cơ chế phòng thủ 4 lớp nghiêm ngặt:
1. **Lớp 1 (Sanitization & PII Scrubbing):** Khử khuẩn chuỗi, loại bỏ các ký tự điều khiển ASCII vô hình, che giấu số điện thoại và email cá nhân bằng biểu thức chính quy (Regex).
2. **Lớp 2 (XML Boundary Isolation):** Đóng gói toàn bộ văn bản review bên trong cặp thẻ cách ly `<customer_review>...</customer_review>` kèm chỉ thị hệ thống nghiêm cấm LLM tuân theo các mệnh lệnh bên trong thẻ.
3. **Lớp 3 (Schema-Constrained Decoding):** Bắt buộc LLM trả về định dạng JSON khớp hoàn toàn với cấu trúc Pydantic `ReviewAnalysis`. Mọi hành vi sinh mã độc, script hay văn bản tự do đều bị Pydantic chặn đứng tại tầng biên giới.
4. **Lớp 4 (Read-Only Database Connection):** Tiến trình phân tích và tác tử chỉ được cấp quyền đọc (`SELECT`) trên cơ sở dữ liệu trong suốt quá trình suy luận.

---

## 3.2. Tiền Xử Lý và Chuẩn Hóa Văn Bản Tiếng Việt Mạng Xã Hội (`normalize.py`)

Khảo sát thực nghiệm trên tập dữ liệu thực tế TikTok Shop tại Tuần 2 cho thấy **53.6%** đánh giá chứa teencode/viết tắt, và **43.2%** đánh giá có độ dài dưới 3 từ. Module `normalize.py` được thiết kế có tham số kiểm soát `enable` (True/False) nhằm phục vụ nghiên cứu bóc tách thành phần (Ablation Study) cho RQ2:

$$\text{Input Review } R \xrightarrow{\text{NFC Normalization}} R_{\text{NFC}} \xrightarrow{\text{Regex Protection}} R_{\text{Protected}} \xrightarrow{\text{Teencode Dictionary}} R_{\text{Expanded}} \xrightarrow{\text{Emoji Mapping}} R_{\text{Normalized}}$$

### Các bước chuẩn hóa cụ thể:
1. **Chuẩn hóa Unicode dựng sẵn (NFC):** Đưa mọi ký tự tiếng Việt về chuẩn NFC thống nhất, loại bỏ dấu rời (NFD).
2. **Bảo vệ ngữ cảnh số lượng & tiền tệ:** Ngăn chặn việc chuyển đổi sai chữ *"k"* (nghìn) thành *"không"* thông qua biểu thức Regex:
   $$\text{"150k"} \xrightarrow{\text{Regex}} \text{"150 nghìn"} \quad (\text{thay vì "150 không"})$$
3. **Rút gọn ký tự kéo dài:** Nén các nguyên âm hoặc dấu câu lặp lại $\ge 3$ lần về 1 ký tự chuẩn (ví dụ: *"đẹppppp"* $\rightarrow$ *"đẹp"*, *"!!!!!!"* $\rightarrow$ *"!"*).
4. **Ánh xạ từ điển Teencode TMĐT:** Tra cứu từ điển hơn 50 từ viết tắt phổ biến (`sp` $\rightarrow$ `sản phẩm`, `sz` $\rightarrow$ `size`, `đc` $\rightarrow$ `được`, `ưng` $\rightarrow$ `ưng ý`, `cskh` $\rightarrow$ `chăm sóc khách hàng`).
5. **Chuyển đổi biểu tượng cảm xúc (Emoji Sentiment Mapping):** Thay thế các emoji phổ biến thành các token cảm xúc có cấu trúc (ví dụ: 😍, 👍 $\rightarrow$ `[EMO_POS]`; 😡, 👎 $\rightarrow$ `[EMO_NEG]`).
6. **Bộ trích xuất cờ nhiễu (Noise Flag Extractor):** Tự động phát hiện 4 cờ: `has_teencode`, `has_emoji`, `is_no_diacritics`, `is_short` để phân loại và đánh giá sâu theo từng phân nhóm dữ liệu.

---

## 3.3. Mô Hình Hóa Toán Học Bài Toán ABSA và Thiết Kế 4 Mô Hình

### 3.3.1. Phát biểu bài toán hình thức (Formal Problem Definition)
Cho một câu phản hồi khách hàng $R = (w_1, w_2, \dots, w_n)$ gồm $n$ từ và một tập hợp gồm 8 khía cạnh chuẩn $\mathcal{A} = \{\text{WATERPROOF}, \text{MATERIAL\_DURABILITY}, \text{FIT\_SIZE}, \text{COMFORT\_USABILITY}, \text{PRICE\_VALUE}, \text{PACKAGING\_SHIPPING}, \text{CUSTOMER\_SERVICE}, \text{ACCESSIBILITY\_DESIGN}\} \cup \{\text{GENERAL}\}$.

Mục tiêu là trích xuất tập hợp các ý kiến $O = \{o_1, o_2, \dots, o_m\}$, trong đó mỗi ý kiến là một bộ 3:
$$o_j = (a_j, s_j, e_j)$$
- $a_j \in \mathcal{A}$ là danh mục khía cạnh.
- $s_j \in \{\text{positive}, \text{negative}, \text{neutral}\}$ là cực tính cảm xúc.
- $e_j \subseteq R$ là đoạn văn bản trích dẫn nguyên văn (verbatim evidence) có độ dài từ 1 đến 15 từ.
- Đồng thời xác định cảm xúc chủ đạo toàn bài $S_{\text{overall}} \in \{\text{positive}, \text{negative}, \text{neutral}\}$ và nhãn thông tin hữu ích $I \in \{0, 1\}$.

### 3.3.2. Thiết kế 3 Đường cơ sở (Baselines) và Mô hình Đề xuất (A1)

| Mô Hình | Loại Kiến Trúc | Kỹ Thuật Trích Xuất & Biểu Diễn | Đặc Điểm Vận Hành | Vai Trò Trong Đồ Án |
| :--- | :--- | :--- | :--- | :--- |
| **B1: Rule-based Lexicon** | Dựa trên tập luật | Từ điển cảm xúc miền áo mưa kết hợp cửa sổ ngữ cảnh (Context Window $W=5$) | Tốc độ cực nhanh, không cần dữ liệu huấn luyện, dễ gãy khi gặp mỉa mai ngầm | Đường cơ sở tối thiểu (Heuristic Baseline) |
| **B2: TF-IDF + Classifier** | Học máy thống kê | Trích xuất N-gram từ/ký tự (1–3 grams) kết hợp Multi-output Logistic Regression | Mô hình gọn nhẹ, huấn luyện nhanh trên CPU, cần tiền xử lý tách từ chuẩn | Đường cơ sở học máy truyền thống (ML Baseline) |
| **B3: ViSoBERT Fine-tuned** | Học sâu Transformer | Kiến trúc XLM-RoBERTa tiền huấn luyện trên 11GB văn bản mạng xã hội tiếng Việt [2] | Fine-tune trên Colab T4, trích xuất biểu diễn ngữ cảnh chuyên sâu | **Đường cơ sở SOTA chuyên ngành** (Deep Learning Baseline) |
| **A1: Proposed LLM Analyzer** | Mô hình Ngôn ngữ Lớn | Gemini Flash kết hợp In-Context Few-Shot Prompting và Pydantic Structured Output | Không cần huấn luyện trọng số, khả năng hiểu mỉa mai và trích xuất bằng chứng verbatim | **Mô hình tác tử đề xuất** (Proposed Approach) |

### 3.3.3. Chi tiết Cấu hình Kỹ thuật và Siêu tham số Huấn luyện
Để đảm bảo tính tái lập (Reproducibility), các tham số kỹ thuật của 4 mô hình được quy định chuẩn hóa:
- **B1 (Rule-based Lexicon):** Xây dựng từ điển 120 từ khóa cảm xúc và 8 khía cạnh đặc thù ngành may mặc/áo mưa, cửa sổ trượt ngữ cảnh $W = 5$ tokens trước và sau từ khóa để nhận diện các tiền tố đảo ngược nghĩa (*không, chẳng, chả, chưa, ko, k*). Khi không phát hiện khía cạnh chuyên ngành, thuật toán tự động gán nhãn `Aspect.GENERAL` nhằm bao phủ toàn diện.
- **B2 (TF-IDF + Logistic Regression):** Áp dụng kiến trúc huấn luyện hai tầng (Two-Tier Architecture):
  - *Tầng 1 (Toàn bài & Macro-Aspects):* Tiền xử lý bằng `underthesea.word_tokenize`, trích xuất N-gram từ/ký tự $(1, 2)$ với `max_features = 10.000` và `sublinear_tf = True`. Huấn luyện bộ phân loại `LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced")` trên tập public benchmark `data/public/train.jsonl`.
  - *Tầng 2 (8 Fine-grained Aspects Áo Mưa):* Tích hợp bộ bọc an toàn `SafeAspectClassifier` huấn luyện trên `data/gold/dev.jsonl`. Nếu một khía cạnh có số mẫu xuất hiện $\ge 2$ cho mỗi cực tính thì tiến hành khớp mô hình Logistic Regression; nếu có $\le 1$ mẫu thì tự động kích hoạt luật fallback về từ điển chuyên ngành, loại bỏ hoàn toàn nguy cơ phát sinh ngoại lệ `ValueError: The number of classes has to be greater than one`. Toàn bộ pipeline được tuần tự hóa vào `models/b2_tfidf_pipeline.joblib`.
- **B3 (ViSoBERT Fine-tuned):** Khởi tạo từ checkpoint `uitnlp/visobert` [2] trên môi trường Google Colab GPU T4 (16GB VRAM); tối ưu bằng AdamW với learning rate $\eta = 2 \times 10^{-5}$, linear warmup tỷ lệ 10%, weight decay 0.01; batch size 16; huấn luyện trong 4 epochs với hàm mất mát Binary Cross-Entropy kết hợp Multi-label Softmax; lưu checkpoint có Macro-F1 cao nhất trên tập validation.
- **A1 (Gemini Flash Analyzer):** Sử dụng model Gemini Flash qua Google GenAI SDK; cung cấp 8 ví dụ Few-Shot đại diện từ `data/gold/dev.jsonl` bao phủ các ca đa khía cạnh, câu teencode, câu không dấu và câu mỉa mai ngầm; cấu hình schema phản hồi cấu trúc nghiêm ngặt thông qua `response_schema=ReviewAnalysis` của Pydantic; cơ chế lưu đệm kết quả (Cache) theo mã băm SHA-256 trên ổ cứng (`data/cache/`) giúp tái lập thí nghiệm tức thì với chi phí $0$ đồng; kèm chiến lược thử lại lũy thừa (Exponential Backoff: 1s, 2s, 4s) và kiểm thực hậu kỳ tính xác thực nguyên văn của trích dẫn bằng chứng (`evidence`).

### 3.3.4. Khung Đánh Giá Thống Kê và Khoảng Tin Cậy Bootstrap (Statistical Evaluation Framework)
Đánh giá hiệu năng mô hình NLP trong môi trường thực tế đòi hỏi sự chặt chẽ về mặt thống kê, vượt lên trên điểm số Macro-F1 tĩnh. EcomReview AI xây dựng module đánh giá độc lập tại `src/ecomreview/eval/metrics.py` gồm 4 chỉ số cốt lõi:
1. **Overall Sentiment Macro-F1:** Trung bình F1 đa lớp trên 3 cực tính (`positive`, `negative`, `neutral`) phản ánh mức độ nhận định cảm xúc chung toàn câu.
2. **Aspect Detection Macro-F1:** Đánh giá khả năng phát hiện đúng sự xuất hiện của từng khía cạnh (nhị phân: có xuất hiện vs không xuất hiện).
3. **End-to-End ABSA Macro-F1:** Chỉ số tổng hợp khắt khe nhất, chấm điểm trên ma trận $\text{Review} \times \text{Aspect}$ với 4 nhãn (`none`, `positive`, `negative`, `neutral`).
4. **Evidence Quote Fidelity (%):** Tỷ lệ các ý kiến mà chuỗi trích dẫn `evidence` nằm nguyên văn từng ký tự trong văn bản gốc review ($e \subseteq R_{\text{raw}}$ hoặc $e \subseteq R_{\text{norm}}$).
5. **Bootstrap 95% Confidence Interval & Paired Bootstrap Test:**
   - Để xác định khoảng biến thiên kỳ vọng, hệ thống thực hiện lấy mẫu lại có hoàn lại theo cấp độ từng review (Cluster-level Bootstrap Resampling) với số lần lặp $B = 2.000$ và cố định $\text{seed} = 42$:
     $$\text{CI}_{95\%} = \left[ \text{Percentile}_{2.5\%}(\text{F1}^*), \; \text{Percentile}_{97.5\%}(\text{F1}^*) \right]$$
   - Kiểm định ý nghĩa cặp (Paired Bootstrap Significance Test) giữa Mô hình $A$ và Mô hình $B$ để tính toán giá trị $p$-value chứng minh mức vượt trội $\Delta\text{F1} = \text{F1}_A - \text{F1}_B$ có ý nghĩa thống kê thực chất ($p < 0.05$).

### 3.3.5. Quy Trình Kiểm Định Độ Tin Cậy Gán Nhãn Độc Lập (Intra-Annotator Cohen's Kappa)
Nhằm giải quyết triệt để nghi ngại của hội đồng học thuật về tính chủ quan khi một cá nhân tự gán nhãn tập dữ liệu (Single-annotator Bias), quy trình kiểm định độ tin cậy được thiết kế nghiêm ngặt:
- Trích xuất ngẫu nhiên 50 mẫu thực tế từ dữ liệu shop, xóa bỏ toàn bộ nhãn lượt 1, xáo trộn thứ tự và xuất ra tệp mù `data/gold/kappa_50_blind.csv`.
- Người nghiên cứu tiến hành gán nhãn lại độc lập sau khoảng cách thời gian $\ge 7$ ngày (để loại bỏ hiệu ứng ghi nhớ ngắn hạn).
- Hệ số **Cohen's Kappa ($\kappa$)** được tính toán tự động qua `sklearn.metrics.cohen_kappa_score` cho cảm xúc toàn bài và từng khía cạnh:
  $$\kappa = \frac{p_o - p_e}{1 - p_e}$$
  trong đó $p_o$ là tỷ lệ đồng thuận quan sát được, $p_e$ là tỷ lệ đồng thuận kỳ vọng ngẫu nhiên. Mức độ tin cậy được đối chiếu theo tiêu chuẩn quốc tế của Landis & Koch (1977) với mục tiêu $\kappa \ge 0.75$.
- Các trường hợp bất đồng giữa hai lượt được tổng hợp vào bảng đối chiếu phục vụ quá trình hiệu đính (Adjudication) để ban hành bộ dữ liệu vàng chuẩn xác `data/gold/gold_v2.jsonl`.

---

## 3.4. Mô Hình Dữ Liệu PostgreSQL và Module Tính Toán Xác Thực (Aggregator Engine)

### 3.4.1. Lược đồ cơ sở dữ liệu quan hệ (Relational Schema)
Toàn bộ dữ liệu được lưu trữ chuẩn hóa trên PostgreSQL 16 qua SQLAlchemy Core:
- **`reviews`:** Lưu trữ đánh giá khách hàng (id, sàn TMĐT, rating, text thô, text đã chuẩn hóa, metadata đơn hàng).
- **`aspect_opinions`:** Lưu kết quả ABSA (review_id, aspect, polarity, evidence, model_source).
- **`insights`:** Lưu các vấn đề cốt lõi và xu hướng do Aggregator phát hiện (aspect, complaint_rate, wilson_lower, wilson_upper, sample_size).
- **`action_proposals`:** Lưu các đề xuất do Planner sinh ra (action_type, title, description, is_marketing, target_metric, evidence_review_ids).
- **`critic_reviews`:** Lưu lịch sử thẩm định của Hybrid Critic (proposal_id, rule_passed, llm_judge_score, feedback, retry_count).

### 3.4.2. Thuật toán Aggregator & Khoảng Tin Cậy Wilson Score (Zero-Hallucination)
Nhằm triệt tiêu 100% rủi ro ảo giác số liệu từ LLM, hệ thống sử dụng thuật toán tính toán xác thực bằng SQL/Python:
Giả sử khía cạnh $a_k$ có tổng số lượt nhắc đến là $n_k$, trong đó có $n_k^{-}$ lượt đánh giá tiêu cực. Tỷ lệ tiêu cực quan sát được là $\hat{p} = \frac{n_k^{-}}{n_k}$.

Để xếp hạng mức độ nghiêm trọng mà không bị thiên lệch bởi các khía cạnh có số mẫu quá nhỏ, hệ thống tính toán **Khoảng tin cậy Wilson Score 95%** ($z = 1.96$):
$$W_{\text{lower}}(\hat{p}, n_k) = \frac{\hat{p} + \frac{z^2}{2n_k} - z \sqrt{\frac{\hat{p}(1-\hat{p})}{n_k} + \frac{z^2}{4n_k^2}}}{1 + \frac{z^2}{n_k}}$$

Chỉ số $W_{\text{lower}}$ được sử dụng làm căn cứ toán học để sắp xếp thứ tự ưu tiên các vấn đề cần giải quyết, hoàn toàn không phụ thuộc vào suy đoán cảm tính của LLM.

---

## 3.5. Kiến Trúc AI Agent State-Graph và Thẩm Định Lai (Hybrid Critic)

### 3.5.1. Máy trạng thái hữu hạn thuần Python (Pure Python State-Graph)
Thay vì phụ thuộc vào các framework cồng kềnh như LangChain hay CrewAI (dễ xung đột thư viện và khó kiểm soát luồng điều phối), hệ thống tự phát triển một State-Graph thuần bằng Python:

$$\mathcal{S} = \{\text{IDLE}, \text{AGGREGATING}, \text{INSIGHT\_GENERATING}, \text{PLANNING}, \text{CRITIQUING}, \text{WAITING\_APPROVAL}, \text{EXECUTED}\}$$

Vòng lặp tự phản biện giữa **Action Planner** và **Hybrid Critic** được giới hạn nghiêm ngặt bởi tham số `CRITIC_MAX_RETRIES = 2`. Nếu sau 2 lần hiệu chỉnh mà đề xuất vẫn không vượt qua kiểm định, hệ thống sẽ đánh dấu `NEEDS_HUMAN_INTERVENTION` và chuyển thẳng về hàng đợi chờ người dùng can thiệp, triệt tiêu hoàn toàn nguy cơ lặp vô tận (Infinite Loop).

### 3.5.2. Bộ 7 Quy Tắc Thẩm Định Xác Thực (Deterministic Rules R1–R7)
Trước khi đưa qua LLM Judge, mọi đề xuất hành động bắt buộc phải vượt qua 7 luật kiểm tra logic cứng:
- **R1 (Insight Grounding):** Mã `insight_ids` trong đề xuất phải tồn tại hợp lệ trong bảng `insights`.
- **R2 (Minimum Evidence Bound):** Đề xuất bắt buộc phải gắn kèm tối thiểu 2 mã đánh giá làm bằng chứng (`len(evidence_review_ids) >= 2`).
- **R3 (Verbatim Authenticity):** Trích dẫn bằng chứng phải trùng khớp 100% với nội dung review thực tế trong database, không được bịa từ.
- **R4 (Functional Categorization):** Phân định rành mạch giữa hành động Marketing (`is_marketing = True`: đổi tiêu đề, cập nhật bảng size, viết kịch bản video, chăm sóc khách hàng) và hành động Vận hành/Sản phẩm (`is_marketing = False`: sửa đường ép nhiệt, đổi chất liệu vải dù).
- **R5 (Resource Feasibility for SMEs):** Ngân sách và thời gian thực thi phải phù hợp với quy mô doanh nghiệp nhỏ (dưới 5 triệu VNĐ, thực hiện trong 1–7 ngày).
- **R6 (E-commerce Policy Compliance):** Nội dung đề xuất không vi phạm chính sách của sàn TMĐT (không kêu gọi giao dịch ngoài sàn, không spam từ khóa cấm).
- **R7 (Termination Guarantee):** Đảm bảo số lần phản biện không vượt quá ngưỡng cho phép (`retry_count <= 2`).

### 3.5.3. Cổng Phê Duyệt Của Con Người (Human Approval Gate)
Đề xuất sau khi vượt qua cả 7 luật xác định và đạt điểm thẩm định của LLM Judge ($\ge 8.0/10.0$) sẽ được hiển thị trên giao diện Streamlit Dashboard. Người quản lý gian hàng giữ quyền tối cao:
- **Chấp thuận (Approve):** Đề xuất được kích hoạt thành kế hoạch hành động chính thức.
- **Yêu cầu sửa đổi (Modify):** Người dùng nhập ghi chú chỉ đạo để Planner tinh chỉnh lại.
- **Từ chối (Reject):** Đề xuất bị hủy bỏ kèm lý do lưu vào nhật ký kiểm toán (Audit Trail).

<!-- CreBy: MenBoyBMN -->
