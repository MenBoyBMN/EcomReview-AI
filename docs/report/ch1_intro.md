# CHƯƠNG 1: GIỚI THIỆU VÀ ĐẶT VẤN ĐỀ NGHIÊN CỨU

> **Đề tài:** EcomReview AI — Hệ thống AI Agent tự động phân tích phản hồi khách hàng tiếng Việt và đề xuất hành động marketing cho doanh nghiệp nhỏ  
> **Tác giả:** Kỹ sư kiêm Nghiên cứu viên dự án EcomReview AI  

---

## 1.1. Bối Cảnh Thực Tiễn và Tầm Quan Trọng Của Vấn Đề

Trong kỷ nguyên kinh tế số, Thương mại Điện tử (TMĐT) và Mua sắm qua Mạng Xã hội (Social Commerce) tại Việt Nam đang chứng kiến tốc độ tăng trưởng vượt bậc. Các nền tảng như **Shopee** và **TikTok Shop** đã trở thành kênh phân phối doanh thu chính cho hàng triệu hộ kinh doanh và doanh nghiệp vừa và nhỏ (SMEs). Trên các sàn giao dịch này, dữ liệu phản hồi từ người tiêu dùng—bao gồm đánh giá sản phẩm (Product Reviews), bình luận tương tác dưới video bán hàng (Comments) và các đoạn hội thoại tư vấn (Chat)—đóng vai trò là nguồn "tài sản số" vô giá, phản ánh trung thực trải nghiệm sử dụng, cảm xúc và các lỗi kỹ thuật phát sinh trong quá trình vận hành thực tế.

Theo các nghiên cứu về hành vi người tiêu dùng trực tuyến, trên 85% người mua sắm tại Việt Nam tham khảo các đánh giá 1 sao đến 3 sao trước khi đưa ra quyết định mua hàng. Một sản phẩm dù có chiến dịch quảng cáo ấn tượng nhưng nếu gặp phải làn sóng phàn nàn về chất lượng (ví dụ: áo mưa bị thấm nước, vải mỏng, rách khóa kéo) mà không có sự phản hồi hoặc cải tiến kịp thời từ người bán, tỷ lệ chuyển đổi (Conversion Rate) và doanh thu có thể sụt giảm từ 30% đến 50% chỉ sau vài tuần. Do đó, việc lắng nghe, phân tích và biến các phản hồi tiêu cực thành hành động khắc phục là điều kiện tiên quyết để các doanh nghiệp nhỏ tồn tại và phát triển bền vững.

---

## 1.2. Khoảng Trống Nghiên Cứu và Những Thách Thức Công Nghệ

Mặc dù nhu cầu phân tích phản hồi là rất lớn, các doanh nghiệp SME tại Việt Nam hiện nay đang đối mặt với ba rào cản công nghệ và phương pháp luận nghiêm trọng:

### 1.2.1. Thách thức ngôn ngữ mạng xã hội tiếng Việt (Vietnamese Social Text Noise)
Khác với văn bản chuẩn mực trong báo chí hay tài liệu học thuật, ngôn ngữ phản hồi TMĐT tại Việt Nam có độ nhiễu cực cao [1], [2], [4], đặc trưng bởi:
- Sử dụng dày đặc từ ngữ tuổi teen (teencode), từ viết tắt không chuẩn hóa (`sp`, `đc`, `ko`, `k`, `h` thay cho *sản phẩm, được, không, giờ*).
- Văn bản không dấu hoặc gõ sai dấu thanh do bộ gõ tiếng Việt.
- Lạm dụng biểu tượng cảm xúc (emoji) để biểu đạt thái độ tiêu cực hoặc khen ngợi.
- Nghệ thuật mỉa mai ngầm (sarcasm/irony), ví dụ: *"Áo chống thấm xịn xò quá, đi mưa 5 phút ướt sũng cả áo trong"*—những câu văn có bề mặt từ ngữ mang tính khen ngợi nhưng bản chất mang cực tính tiêu cực sâu sắc.

### 1.2.2. Khoảng trống "Từ Thấu Hiểu Đến Hành Động" (Insight-to-Action Gap)
Các hệ thống Social Listening và công cụ NLP hiện có trên thị trường chủ yếu dừng lại ở bài toán Phân loại Cảm xúc Toàn văn (Document-level Sentiment Analysis)—tức chỉ dán nhãn toàn bộ bình luận là Tích cực hay Tiêu cực, hoặc đếm tần suất các từ khóa chung chung. Cách tiếp cận này để lại một khoảng trống lớn giữa khâu phân tích dữ liệu và ra quyết định thực chiến [14], [20]:
- Nhà bán hàng không biết được chính xác **khía cạnh cụ thể nào** (độ chống thấm, chất vải, form dáng, dịch vụ giao hàng) đang bị chê trách [3], [5].
- Hệ thống không có khả năng tự động đề xuất **hành động cụ thể** (Cần sửa bảng kích thước trên Shopee hay phải quay video hướng dẫn mặc áo đúng cách trên TikTok?) tương thích với nguồn lực có hạn của một shop nhỏ.

### 1.2.3. Vấn đề Ảo giác Số liệu (Hallucination) của Mô Hình Ngôn Ngữ Lớn (LLM)
Sự trỗi dậy của các Mô hình Ngôn ngữ Lớn (như GPT-4, Gemini) mở ra tiềm năng tự động hóa việc tóm tắt và ra quyết định [7], [8]. Tuy nhiên, khi áp dụng trực tiếp theo phương pháp Single-Prompt (hỏi một câu để LLM trả lời tất cả), các mô hình này bộc lộ điểm yếu chết người: **tự bịa số liệu thống kê (hallucination)** và thiếu khả năng tự phản biện nghiêm ngặt [10], [17]. LLM có thể dễ dàng viết: *"Có 65% khách hàng phàn nàn về đường may"* mà hoàn toàn không có bất kỳ truy vấn cơ sở dữ liệu thực tế nào hỗ trợ. Trong môi trường kinh doanh thực chiến, việc ra quyết định nhập hàng hay đổi nhà xưởng dựa trên số liệu "ảo" có thể dẫn đến thiệt hại tài chính nghiêm trọng.

---

## 1.3. Mục Tiêu và Đối Tượng Nghiên Cứu

### 1.3.1. Mục tiêu Nghiên cứu
Đề tài **EcomReview AI** hướng tới mục tiêu kép (Dual-Objective):
1. **Về mặt Khoa học & Học thuật:** 
   - Xây dựng một quy trình phân tích cảm xúc theo khía cạnh (Aspect-Based Sentiment Analysis - ABSA) tiếng Việt đạt độ chính xác cao, có khả năng thích nghi chuyển miền (Domain Adaptation) từ dữ liệu benchmark công khai sang miền chuyên ngành hẹp của doanh nghiệp nhỏ.
   - Thiết kế và kiểm chứng thực nghiệm kiến trúc đại lý thông minh đa bước có kiểm chứng (`SQL Aggregator` $\rightarrow$ `Insight Engine` $\rightarrow$ `Action Planner` $\rightleftarrows$ `Hybrid Critic`), chứng minh khả năng triệt tiêu lỗi ảo giác số liệu và đảm bảo 100% tính căn cứ thực tế (Groundedness).
2. **Về mặt Kỹ thuật & Ứng dụng Thực tiễn:**
   - Xây dựng một hệ thống hoàn chỉnh từ Backend (FastAPI, PostgreSQL 16) đến Giao diện người dùng (Streamlit Dashboard 4 trang) trực quan, có cổng phê duyệt của con người (Human-in-the-Loop).
   - Đóng gói giải pháp dưới dạng container Docker Compose 1-click, sẵn sàng chuyển giao cho các chủ shop online triển khai tức thì.

### 1.3.2. Đối tượng và Phạm vi Nghiên cứu
- **Đối tượng nghiên cứu:** Phản hồi của người tiêu dùng bằng tiếng Việt trên các sàn TMĐT (Shopee) và mạng xã hội mua sắm (TikTok Shop).
- **Trường hợp điển hình (Case Study):** Ngành hàng **Áo Mưa thời trang & tiện lợi**—một sản phẩm tiêu biểu cho nhóm hàng tiêu dùng thiết yếu có tính thời vụ cao, vòng đời ngắn, và nhạy cảm mạnh mẽ với thời tiết và công năng kỹ thuật (chống thấm, độ bền nhiệt, kích thước che phủ).

---

## 1.4. Ba Câu Hỏi Nghiên Cứu (Research Questions)

Đề tài được cấu trúc xoay quanh 3 câu hỏi nghiên cứu cốt lõi:

* **Câu hỏi 1 (RQ1 - Hiệu năng ABSA và Thích nghi miền):**  
  *Khi phân tích phản hồi khách hàng TMĐT tiếng Việt, mô hình ngôn ngữ lớn (Gemini Flash few-shot với Structured Output) so với 3 thế hệ đường cơ sở (Rule-based, TF-IDF + Logistic Regression, Pretrained ViSoBERT) đạt hiệu quả như thế nào về Macro-F1, độ trễ, chi phí và khả năng thích nghi khi chuyển từ tập chuẩn chung sang miền hẹp Shop Áo Mưa?*

* **Câu hỏi 2 (RQ2 - Đóng góp của Chuẩn hóa tiếng Việt mạng xã hội):**  
  *Module tiền xử lý và chuẩn hóa văn bản mạng xã hội (giải mã teencode, chuẩn hóa dấu thanh, xử lý emoji) tác động định lượng thế nào đến từng dòng kiến trúc mô hình và từng lát cắt dữ liệu có độ nhiễu cao?*

* **Câu hỏi 3 (RQ3 - Tính Căn cứ và An toàn của AI Agent Đa Bước):**  
  *Kiến trúc Agent đa bước có kiểm chứng kết hợp phê bình lặp (`Planner ⇄ Hybrid Critic`) có tạo ra các đề xuất hành động marketing có căn cứ thực tế, đúng số liệu và an toàn hơn đáng kể so với phương pháp Single-Prompt Baseline hay không?*

---

## 1.5. Đóng Góp Của Đề Tài (Scientific and Practical Contributions)

1. **Bộ Taxonomy 8 khía cạnh chuyên sâu kết hợp Kiến trúc Khía cạnh Hai tầng:** Thiết lập hệ thống phân loại chuẩn mực cho ngành hàng may mặc/áo mưa, đồng thời xây dựng ánh xạ về 5 nhóm vĩ mô chung của TMĐT giúp thực hiện đánh giá chuyển miền một cách nhất quán.
2. **Đánh giá thực nghiệm so sánh đa thế hệ (Multi-generational Benchmarking):** Cung cấp kết quả so sánh toàn diện trên cùng một tập kiểm thử tiếng Việt giữa 4 phương pháp đại diện cho 4 giai đoạn tiến hóa của NLP: Bộ luật (Rule) $\rightarrow$ Học máy cổ điển (TF-IDF + ML) $\rightarrow$ Pretrained Transformer chuyên biệt tiếng Việt mạng xã hội (ViSoBERT) $\rightarrow$ Mô hình Ngôn ngữ Lớn đa năng (Gemini Flash).
3. **Mô hình Agent State-Graph thuần có cơ chế thẩm định lai (Hybrid Critic):** Đề xuất kiến trúc Agent tinh gọn bằng Python State-Graph, tách biệt hoàn toàn giữa tầng tính toán số liệu xác định (Deterministic SQL Aggregation) và tầng suy luận sáng tạo (Generative Planning), bảo vệ doanh nghiệp trước rủi ro Prompt Injection và ảo tưởng dữ liệu.
4. **Sản phẩm ứng dụng hoàn chỉnh có thể chuyển giao:** Một ứng dụng web dashboard hoàn chỉnh kèm tài liệu API, bộ kiểm thử tự động đạt độ phủ cao và kịch bản triển khai Docker chỉ với một câu lệnh.

---

## 1.6. Cấu Trúc Toàn Văn Báo Cáo

Báo cáo nghiên cứu được tổ chức thành 5 chương chính:
- **Chương 1: Giới thiệu và Đặt vấn đề nghiên cứu** — Trình bày bối cảnh, khoảng trống công nghệ, mục tiêu, các câu hỏi nghiên cứu và đóng góp khoa học của đề tài.
- **Chương 2: Cơ sở Lý thuyết và Tổng quan Công trình Liên quan** — Tổng hợp và phân tích 20+ công trình nghiên cứu về ABSA tiếng Việt, Pretrained Language Models, kỹ thuật Structured Output trên LLM, và kiến trúc AI Agent có phản hồi tự phê bình.
- **Chương 3: Phương Pháp Đề Xuất và Kiến Trúc Hệ Thống** — Trình bày chi tiết pipeline chuẩn hóa văn bản, thiết kế 3 Baseline và mô hình phân tích Gemini, kiến trúc Agent State-Graph, 7 quy tắc Critic xác định và mô hình cơ sở dữ liệu.
- **Chương 4: Thực Nghiệm, Kết Quả Đánh Giá và Phân Tích Lỗi** — Công bố kết quả thực nghiệm giải quyết RQ1, RQ2, RQ3 có kiểm định Bootstrap CI 95%, phân tích hiện tượng chuyển miền và cây phân tích lỗi Pareto.
- **Chương 5: Kết Luận và Hướng Phát Triển** — Tổng kết các phát hiện chính, ranh giới hạn chế của nghiên cứu và định hướng mở rộng hệ thống trong tương lai.

<!-- CreBy: MenBoyBMN -->

