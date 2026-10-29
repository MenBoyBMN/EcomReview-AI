# CHƯƠNG 2: CƠ SỞ LÝ THUYẾT VÀ TỔNG QUAN CÔNG TRÌNH LIÊN QUAN

> **Báo cáo nghiên cứu học thuật:** EcomReview AI — Hệ thống AI Agent tự động phân tích phản hồi khách hàng tiếng Việt và lập kế hoạch hành động marketing cho doanh nghiệp vừa và nhỏ.  
> **Tổng quan công trình:** 20 công trình khoa học chuẩn mực đã xác minh mã định danh số (DOI/arXiv) và phân nhóm theo 5 trụ cột lý thuyết cốt lõi.  
> **Quy chuẩn trích dẫn:** IEEE Reference Format ([1]–[20]) đồng bộ trực tiếp với cơ sở dữ liệu `docs/references.bib`.

---

## 2.1. Phân Tích Cảm Xúc Theo Khía Cạnh (ABSA) và Đặc Thù Tiếng Việt Trên Thương Mại Điện Tử

### 2.1.1. Cấu trúc bài toán Phân tích cảm xúc theo khía cạnh (Aspect-Based Sentiment Analysis - ABSA)
Trong kỷ nguyên số, dữ liệu nhận xét của người dùng (Customer Reviews) trên các nền tảng thương mại điện tử (Shopee, TikTok Shop, Lazada) đã trở thành tài sản chiến lược phản ánh trực tiếp trải nghiệm người tiêu dùng. Tuy nhiên, các kỹ thuật phân tích cảm xúc truyền thống ở cấp độ văn bản (Document-level) hoặc cấp độ câu (Sentence-level) [6], [20] bộc lộ hạn chế chí mạng: không thể giải quyết được hiện tượng nhận xét đa chiều có cảm xúc hỗn hợp (Mixed Sentiments). Một khách hàng hoàn toàn có thể khen ngợi: *"Giao hàng siêu nhanh, đóng gói đẹp nhưng áo mưa vừa mặc đi mưa to đã ngấm nước ướt hết lưng"*. Nếu chỉ gán nhãn chung là "Tích cực" hoặc "Tiêu cực", doanh nghiệp sẽ bỏ lỡ hoàn toàn thông tin quan trọng về khiếm khuyết sản phẩm.

Để giải quyết bài toán trên, phân tích cảm xúc theo khía cạnh (ABSA) được giới thiệu và chuẩn hóa thông qua chuỗi hội thảo quốc tế SemEval [14]. Theo khảo sát toàn diện của Zhang et al. (2022) [10], bài toán ABSA tổng quát có thể phân rã thành bốn nhiệm vụ con cốt lõi:
1. **Aspect Term Extraction (ATE):** Nhận diện cụ thể các từ/cụm từ đại diện cho đối tượng được đánh giá trong câu (ví dụ: *"đường may"*, *"khóa kéo"*).
2. **Aspect Category Detection (ACD):** Ánh xạ nhận xét vào các khía cạnh định trước thuộc danh mục phân loại (Aspect Taxonomy) của miền sản phẩm (ví dụ: gán vào khía cạnh `WATERPROOF` hoặc `FIT_SIZE`).
3. **Aspect Sentiment Classification (ASC):** Xác định cực tính cảm xúc $s \in \{\text{positive}, \text{negative}, \text{neutral}\}$ đối với từng khía cạnh cụ thể.
4. **End-to-End Compound ABSA:** Trích xuất đồng thời bộ ba hoặc bộ bốn $T = (a, c, s, e)$ gồm cụm từ khía cạnh ($a$), danh mục ($c$), cực tính ($s$), và đoạn trích bằng chứng ($e$).

Đề tài **EcomReview AI** áp dụng mô hình End-to-End Compound ABSA có cấu trúc, trong đó mỗi phản hồi khách hàng được trích xuất thành danh sách các bộ dữ liệu `AspectOpinion` tuân thủ nghiêm ngặt 8 khía cạnh chuẩn mực của ngành hàng áo mưa thời trang và tiện lợi.

### 2.1.2. Tiến trình phát triển các bộ dữ liệu và mô hình ABSA tiếng Việt
Tại Việt Nam, nghiên cứu về ABSA khởi sắc với chiến dịch đánh giá ngôn ngữ VLSP 2018 [5], tập trung vào hai miền dữ liệu truyền thống là nhà hàng và khách sạn với phương pháp học máy thống kê (Maximum Entropy, Support Vector Machines - SVM). Sau đó, nhóm nghiên cứu tại Trường ĐH Công nghệ Thông tin (ĐHQG-HCM) đã mở rộng bài toán sang môi trường học đường với bộ ngữ liệu UIT-VSFC [6].

Bước ngoặt lớn đối với ABSA trong thương mại điện tử tiếng Việt là công trình của Luc Phan et al. (2021) với bộ dữ liệu **UIT-ViSFD** (Vietnamese Smartphone Feedback Dataset) [7]. Gồm 11.122 phản hồi thực tế từ người mua điện thoại, UIT-ViSFD thiết lập một chuẩn đánh giá khắt khe trên 10 khía cạnh kỹ thuật và dịch vụ. Luc Phan et al. ứng dụng mạng hồi quy Bi-LSTM kết hợp vector từ fastText để xây dựng hệ thống lắng nghe mạng xã hội SA2SL. Tiếp đó, các biến thể mở rộng như UIT-ViSD4SA [8] sử dụng PhoBERT-CRF để trích xuất ranh giới span cảm xúc, và mô hình Biaffine Attention [9] đã nâng cao đáng kể độ chính xác bắt cặp khía cạnh - cảm xúc. 

Tuy nhiên, toàn bộ các nghiên cứu trên ([5]–[9]) đều chỉ dừng lại ở bài toán phân loại tĩnh và thống kê mô tả; chưa từng có công trình nào tích hợp lớp suy luận tác tử (Agent) để tự động chuyển hóa kết quả phân loại thành các đề xuất hành động kinh doanh cụ thể cho doanh nghiệp vừa và nhỏ (SMEs).

### 2.1.3. Thách thức ngôn ngữ mạng xã hội và kỹ thuật tiền xử lý tiếng Việt
Văn bản phản hồi trên các nền tảng thương mại điện tử như TikTok Shop và Shopee mang tính phi hình thức (Informal Social Text) rất cao. Các hiện tượng đặc trưng bao gồm:
- **Teencode và viết tắt:** Tần suất xuất hiện dày đặc các biến thể như *"ko"*, *"k"*, *"kh"*, *"hok"* (không); *"sp"* (sản phẩm); *"đc"*, *"dc"* (được); *"sz"* (size); *"cskh"* (chăm sóc khách hàng)... Thống kê thực tế tại Tuần 2 trên dữ liệu shop áo mưa cho thấy **53.6%** đánh giá thực tế chứa teencode.
- **Kéo dài ký tự cảm thán:** Người dùng kéo dài các nguyên âm hoặc dấu câu để nhấn mạnh cảm xúc (*"mỏnggggg"*, *"đẹppppp"*, *"quá tệ!!!!!!"*).
- **Văn bản không dấu và đánh giá cụt ngủn:** Khoảng 43.2% nhận xét có độ dài dưới 3 từ (*"đẹp"*, *"tốt"*, *"ok"*), đặt ra yêu cầu phải có bộ lọc tính hữu ích thông tin (`informative`).
- **Mỉa mai và khen chê trái ngược (Sarcasm & Implicit Negation):** Ví dụ: *"Chống thấm đỉnh thật sự, mới đi mưa 5 phút đã ướt sũng cả người"* — bề ngoài dùng từ ngữ khen ngợi nhưng bản chất là phản hồi tiêu cực gay gắt.

Các mô hình ngôn ngữ tiền huấn luyện tổng quát như PhoBERT [1] hoặc bộ công cụ tách từ VnCoreNLP [3] được huấn luyện trên văn bản báo chí chuẩn mực, do đó rất dễ xảy ra hiện tượng phân rã token sai lệch khi đối mặt với văn bản mạng xã hội. Để khắc phục, công trình của Nguyen et al. (2020) [4] đã chứng minh hiệu quả của việc tiền xử lý chuẩn hóa văn bản mạng xã hội trước khi đưa vào mô hình cảm xúc. Trong đề tài này, chúng tôi phát triển module `normalize.py` tích hợp từ điển teencode TMĐT độc quyền, cho phép bật/tắt linh hoạt nhằm phục vụ thực nghiệm bóc tách thành phần (Ablation Study) trả lời trực tiếp cho câu hỏi nghiên cứu RQ2.

---

## 2.2. Mô Hình Ngôn Ngữ Tiền Huấn Luyện Và Mô Hình Ngôn Ngữ Lớn (LLM) Có Cấu Trúc

### 2.2.1. Sự trỗi dậy của ViSoBERT trong xử lý ngôn ngữ mạng xã hội tiếng Việt
Để giải quyết bài toán biểu diễn ngữ nghĩa cho văn bản phi chuẩn mực, Nguyen et al. (2023) [2] đã công bố **ViSoBERT** — mô hình ngôn ngữ dựa trên kiến trúc XLM-RoBERTa được tiền huấn luyện trên 11GB văn bản tiếng Việt thu thập từ các nền tảng mạng xã hội (Facebook, YouTube, TikTok). Nhờ tập từ vựng (Vocabulary) được tối ưu hóa đặc thù cho ngôn ngữ giao tiếp mạng xã hội, ViSoBERT đã thiết lập kỷ lục hiệu năng (SOTA) mới trên 6 tác vụ NLP tiếng Việt, vượt trội hơn đáng kể so với PhoBERT [1]. Trong khuôn khổ đồ án EcomReview AI, ViSoBERT được lựa chọn làm **Mô hình Cơ sở Tiêu chuẩn (Baseline B3)** để đại diện cho nhánh mô hình học sâu phân loại nhỏ được fine-tune chuyên biệt.

### 2.2.2. So sánh giữa Mô hình nhỏ tinh chỉnh (Fine-tuned SLMs) và Mô hình ngôn ngữ lớn (LLMs)
Nghiên cứu đột phá SentiEval của Zhang et al. (2024) tại NAACL [11] đã tiến hành một cuộc kiểm định thực tế (Reality Check) về năng lực phân tích cảm xúc giữa các mô hình ngôn ngữ lớn (LLMs như GPT-3.5, GPT-4, LLaMA) và các mô hình nhỏ được tinh chỉnh (Fine-tuned Small LMs như RoBERTa, DeBERTa). Kết quả thực nghiệm chỉ ra rằng:
- Dưới thiết lập Zero-shot hoặc Few-shot thông thường, LLMs thường gặp khó khăn trong việc nhận diện chính xác các sắc thái cảm xúc ngầm và thuật ngữ chuyên ngành so với các mô hình chuyên biệt được tinh chỉnh trên tập dữ liệu đích.
- Tuy nhiên, LLMs thể hiện năng lực tổng quát hóa vượt bậc, khả năng hiểu ngữ cảnh phức tạp, nhận diện mỉa mai ngầm và đặc biệt là khả năng suy luận logic theo chuỗi (Chain-of-Thought) vượt xa các mô hình học sâu truyền thống.

Nghiên cứu này là tiền đề trực tiếp thúc đẩy chúng tôi xây dựng Câu hỏi Nghiên cứu 1 (**RQ1**): Liệu mô hình ngôn ngữ lớn thế hệ mới (Gemini Flash) với cơ chế giải mã ràng buộc schema có thể vượt qua hoặc tương đương với ViSoBERT được fine-tune trên dữ liệu TMĐT tiếng Việt hay không?

### 2.2.3. Trích xuất thông tin ràng buộc Schema (Schema-Constrained Structured Output)
Một trở ngại lớn nhất khi ứng dụng LLMs vào các hệ thống phần mềm thương mại là tính bất định (Non-determinism) của văn bản tự do, dẫn đến lỗi phân tích cú pháp (Syntax Parse Error) và hiện tượng ảo giác (Hallucination). Nghiên cứu ChatABSA của Bai et al. (2024) [12] đã chỉ ra rằng việc sử dụng các cấu trúc gợi ý có kiểm soát (Constrained Prompting) giúp nâng cao đáng kể độ chính xác của bài toán ABSA phức hợp.

Trong EcomReview AI, chúng tôi nâng tầm kỹ thuật này lên mức kiểm soát công nghiệp bằng cách kết hợp:
1. **Pydantic v2 Schema Enforcement:** Ép buộc mô hình Gemini Flash sinh mã JSON tuân thủ tuyệt đối cấu trúc dữ liệu `ReviewAnalysis` thông qua tham số `response_schema` của bộ công cụ `google-genai`. Mọi đầu ra sai lệch kiểu dữ liệu hoặc vi phạm ràng buộc danh mục đều bị chặn đứng ngay tại tầng biên giới dữ liệu.
2. **Biểu diễn ngữ nghĩa đa chiều với BGE-M3:** Nghiên cứu của Chen et al. (2024) [13] cung cấp nền tảng cho việc nhúng ngữ nghĩa dày đặc và truy xuất các đánh giá tương đồng phục vụ trích xuất bằng chứng xác thực.

---

## 2.3. Kiến Trúc Tác Tử Tự Trị (AI Agent), Vòng Lặp Phản Tư (Self-Reflection) Và Kiểm Định Độ Trung Thực

### 2.3.1. Các mô hình kiến trúc tác tử: ReAct, Reflexion và Self-Refine
Nhằm vượt qua giới hạn của việc tương tác một lượt (Single-turn generation), các kiến trúc tác tử AI tự trị đã phát triển vượt bậc:
- **ReAct (Yao et al., 2023) [15]:** Kết hợp hài hòa giữa suy luận (Reasoning) và hành động (Acting). Tác tử luân phiên tạo suy nghĩ (*Thought*), gọi công cụ thực thi (*Action*), và tiếp nhận kết quả quan sát (*Observation*). Phương pháp này giúp tác tử biết tự tra cứu thông tin thực tế trước khi đưa ra nhận định.
- **Self-Refine (Madaan et al., 2023) [16]:** Khởi xướng cơ chế tự phê bình không cần huấn luyện lại mô hình. Một module phát sinh nội dung sơ thảo (Generator), sau đó module phản biện (Critic) cung cấp nhận xét đa tiêu chí, và Generator tiến hành hiệu chỉnh lặp lại cho đến khi đạt tiêu chuẩn nghiệm thu.
- **Reflexion (Shinn et al., 2023) [17]:** Nâng cấp Self-Refine bằng cách lưu trữ các bài học kinh nghiệm và lỗi sai vào bộ nhớ ngôn ngữ (Semantic Memory). Nhờ đó, tác tử có khả năng ghi nhớ các sai sót trong quá khứ để không tái phạm trong các lượt thực thi tiếp theo.

### 2.3.2. Rủi ro ảo giác, hiện tượng tự xác nhận và giải pháp Hybrid Critic
Mặc dù Self-Refine và Reflexion mang lại tiềm năng to lớn, nghiên cứu của Zheng et al. (2023) về LLM-as-a-Judge [18] đã vạch trần các điểm yếu nội tại của việc dùng LLM làm giám khảo đánh giá:
1. **Thiên vị tự xác nhận (Self-Confirmation Bias):** Khi một mô hình LLM tự đánh giá nội dung do chính nó sinh ra, nó có xu hướng chấm điểm cao hơn thực tế và bỏ qua các lỗi logic tinh vi.
2. **Thiên vị độ dài (Verbosity Bias):** LLM có khuynh hướng đánh giá các phản hồi dài dòng, trau chuốt là tốt hơn, bất chấp nội dung đó có thể thiếu khả thi hoặc xa rời dữ liệu gốc.
3. **Ảo giác số liệu thống kê (Metric Hallucination):** Nếu để LLM tự tính toán phần trăm, điểm trung bình hoặc tổng số lượng review, mô hình thường xuyên tạo ra số liệu giả mạo nhưng nghe có vẻ thuyết phục.

Để giải quyết triệt để vấn đề này, **EcomReview AI đề xuất kiến trúc bất biến Hybrid Critic**:
- **Tầng 1 (Tách biệt tuyệt đối việc tính toán số liệu):** 100% các chỉ số tổng hợp (tỷ lệ phàn nàn, xếp hạng khía cạnh tiêu cực, khoảng tin cậy Wilson Score) được tính toán bằng SQL thuần trên PostgreSQL hoặc Python xác định (`Aggregator`), tuyệt đối không để LLM can thiệp vào phép tính số học.
- **Tầng 2 (Phản biện dựa trên 7 luật xác định R1–R7):** Kiểm tra cứng các điều kiện tiên quyết: mã `insight_id` tồn tại, tối thiểu 2 mã `review_id` làm bằng chứng thực tế, trích dẫn nguyên văn không bịa đặt, ngân sách marketing khả thi cho SMEs.
- **Tầng 3 (LLM-Judge có rubric định lượng):** Chỉ sau khi vượt qua 7 luật xác định, đề xuất mới được đưa qua LLM Critic để đánh giá tính logic ngôn ngữ và tính thực chiến.

### 2.3.3. Đo lường tính căn cứ (Groundedness) và khả thi trong kinh doanh
Đánh giá độ tin cậy của đề xuất hành động marketing đòi hỏi một khung đo lường chặt chẽ tương tự như tiêu chuẩn đo độ trung thực (Faithfulness) trong các hệ thống RAG (RAGAS - Es et al., 2024 [19]). Trong EcomReview AI, chúng tôi mở rộng nguyên lý của RAGAS thành hai chỉ số định lượng phục vụ câu hỏi nghiên cứu RQ3:
- **Groundedness Score ($G$):** Tỷ lệ các luận điểm trong đề xuất hành động có thể truy vết chính xác về ít nhất 2 câu trích dẫn bằng chứng verbatim trong tập review gốc:
  $$G = \frac{\sum_{i=1}^{M} \mathbb{I}(\text{Traceable}(P_i, R_{\text{evidence}} \ge 2))}{M}$$
- **Actionability & Feasibility Score ($A$):** Điểm đánh giá mức độ khả thi thực chiến đối với doanh nghiệp nhỏ (phân định rõ ràng giữa hành động Marketing như đổi tiêu đề, chạy quảng cáo, cập nhật mô tả so với hành động Vận hành như đổi xưởng may, cải tiến dây chuyền).

---

## 2.4. Phân Tích Khoảng Trống Nghiên Cứu (Research Gaps) Và Định Vị Của EcomReview AI

Dựa trên việc khảo sát và đối sánh 20 công trình khoa học tiêu biểu, chúng tôi lập bảng tổng kết các khoảng trống nghiên cứu hiện hữu và định vị đóng góp học thuật của đề tài:

| Tiêu Chí Đối Sánh | Hệ Thống ABSA Truyền Thống ([5]–[9]) | Nghiên Cứu LLM Cho ABSA ([10]–[14]) | Các Hệ Thống AI Agent Hiện Đại ([15]–[18]) | **Hệ Thống Đề Xuất: EcomReview AI** |
| :--- | :---: | :---: | :---: | :---: |
| **Ngôn ngữ mục tiêu** | Tiếng Việt | Đa số tiếng Anh / Đa ngữ | Đa số tiếng Anh | **Tiếng Việt mạng xã hội & TMĐT** |
| **Miền áp dụng** | Nhà hàng, Khách sạn, Smartphone | Tổng quát / Benchmark mở | Lập trình, Game, WebShop | **Áo mưa thời trang & Tiện lợi (SMEs)** |
| **Phương pháp phân loại cốt lõi** | Bi-LSTM, PhoBERT, SVM | Zero/Few-shot LLMs | LLM Prompting tự do | **Dual-Track: ViSoBERT (B3) vs Gemini Flash (A1)** |
| **Xử lý nhiễu mạng xã hội (Teencode)** | Giới hạn / Chưa chuyên sâu | Phụ thuộc tokenizer LLM | Không tập trung xử lý | **Module `normalize.py` đo Ablation độc lập (RQ2)** |
| **Tính toàn vẹn của số liệu** | Tính trực tiếp trên dataset | LLM tự phỏng đoán số liệu | Thường xuyên ảo giác số liệu | **Zero-Hallucination SQL/Python Aggregator** |
| **Từ phân tích đến hành động** | ❌ Chỉ dừng ở gán nhãn | ❌ Không có đề xuất hành động | ⚠️ Đề xuất chung chung, không gắn bằng chứng | **Action Planner có Playbook miền áo mưa (12 hành động chuẩn)** |
| **Cơ chế tự phản biện & bảo vệ** | ❌ Không có | ❌ Không có | ⚠️ Tự phản biện bằng prompt (dễ thiên vị) | **Hybrid Critic (7 Luật cứng R1–R7 + LLM Judge)** |
| **Phòng thủ Prompt Injection** | ❌ Không có | ❌ Bị bỏ ngỏ | ⚠️ Rất dễ bị đánh lừa qua review rác | **Defense-in-Depth 4 lớp (XML, Schema, Read-only)** |
| **Kiểm định thống kê học thuật** | Đôi khi có F1 | Đôi khi có Accuracy | Hiếm khi có kiểm định thống kê | **Bootstrap CI 95% ($B=1.000$) & Blind A/B (RQ3)** |

### Kết luận Chương 2:
Tổng quan 20 công trình khoa học trên khẳng định tính cấp thiết, tính mới và giá trị ứng dụng cao của **EcomReview AI**. Bằng cách kết hợp giữa tính chặt chẽ của các mô hình học sâu truyền thống (ViSoBERT) và năng lực tổng quát hóa của mô hình ngôn ngữ lớn (Gemini Flash), kết hợp vòng lặp tác tử tự phê bình Hybrid Critic và tri thức miền thực chiến, đồ án khỏa lấp trọn vẹn khoảng trống giữa nghiên cứu học thuật về khai phá quan điểm và nhu cầu thực tiễn của doanh nghiệp vừa và nhỏ Việt Nam.

<!-- CreBy: MenBoyBMN -->
