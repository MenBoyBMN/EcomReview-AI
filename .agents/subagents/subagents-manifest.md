# Danh Mục Subagents Phục Vụ Dự Án (Subagents Manifest)

Tài liệu này định nghĩa các vai trò Subagent chuyên biệt có thể được triệu hồi thông qua `invoke_subagent` để giải quyết các mảng công việc phức tạp, độc lập trong suốt 10 tuần phát triển **EcomReview AI**.

---

## 1. `critic-reviewer` (Chuyên Gia Phản Biện Mã Nguồn & 7 Luật Xác Định)
- **Tập tin đặc tả:** `.AGENTS/subagents/critic-reviewer.md`
- **Vai trò:** Phản biện chéo độc lập, loại bỏ thiên kiến tự xác nhận, bắt lỗi `git diff`.
- **Trách nhiệm chính:**
  - Soi chiếu toàn bộ `git diff` trước khi merge/commit để phát hiện rò rỉ bộ nhớ, Null reference, N+1 query.
  - Kiểm tra xem code có vi phạm nguyên tắc Minimal Diff hoặc phát sinh Scope Creep không.
  - Kiểm định sự tuân thủ tuyệt đối 7 luật xác định (R1–R7) trong `playbook_aomua.yaml`.
- **Môi trường hoạt động:** Toàn bộ repository (chế độ Read-Only trên `git diff`).

---

## 2. `codebase-explorer` (Trinh Sát Mã Nguồn & Phân Tích Call-Graph)
- **Tập tin đặc tả:** `.AGENTS/subagents/codebase-explorer.md`
- **Vai trò:** Khảo sát diện rộng, truy vết luồng dữ liệu E2E và bảo vệ Main Agent khỏi ngộ độc ngữ cảnh.
- **Trách nhiệm chính:**
  - Khảo sát các luồng dữ liệu phức tạp đi qua nhiều tầng (Database $\rightarrow$ Agent $\rightarrow$ API $\rightarrow$ UI).
  - Đọc 20–50 file trong không gian riêng biệt, sau đó tóm tắt danh sách file/hàm cụ thể cần sửa cho Main Agent.
  - Phân tích rủi ro phụ thuộc (Call Graph dependencies) trước khi thực hiện phẫu thuật mã nguồn.
- **Môi trường hoạt động:** Toàn bộ repository (chế độ Read-Only).

---

## 3. `absa_ml_engineer` (Kỹ Sư Mô Hình & Đánh Giá NLP)
- **Vai trò:** Xây dựng, huấn luyện và đánh giá các mô hình phân loại khía cạnh cảm xúc (ABSA).
- **Trách nhiệm chính:**
  - Viết code pipeline cho Baseline B1 (Rule/Lexicon), B2 (TF-IDF + Logistic Regression).
  - Chuẩn bị notebook fine-tune ViSoBERT B3 trên Colab T4.
  - Tích hợp Gemini Flash A1 với Pydantic Structured Output.
  - Tính toán Macro-F1, Confusion Matrix, và Bootstrap CI 95% ($B=1.000$).
- **Môi trường hoạt động:** `src/ecomreview/analyze/`, `src/ecomreview/eval/`, `notebooks/`.

---

## 4. `agent_architect` (Kiến Trúc Sư AI Agent & Database)
- **Vai trò:** Thiết kế luồng State-Graph, cấu trúc dữ liệu PostgreSQL và cơ chế phản biện Hybrid Critic.
- **Trách nhiệm chính:**
  - Thiết kế bảng PostgreSQL 16 và các câu lệnh truy vấn Aggregator (Wilson score, không ảo giác).
  - Xây dựng module `InsightEngine` và bộ tri thức `knowledge/playbook_aomua.yaml`.
  - Cài đặt `ActionPlanner` và `HybridCritic` (7 luật R1–R7 + LLM Judge).
  - Vận hành State-Graph Orchestrator kèm tính năng ghi log trace JSON phục vụ phân tích.
- **Môi trường hoạt động:** `src/ecomreview/agent/`, `src/ecomreview/db/`, `knowledge/`.

---

## 5. `fullstack_engineer` (Kỹ Sư Triển Khai Giao Diện & Docker)
- **Vai trò:** Xây dựng API backend, Dashboard tương tác và đóng gói container.
- **Trách nhiệm chính:**
  - Phát triển FastAPI endpoints phục vụ phân tích review và sinh kế hoạch.
  - Xây dựng Streamlit Dashboard 4 trang trực quan với Plotly (kèm luồng duyệt/sửa kế hoạch Human-in-the-loop).
  - Soạn thảo `Dockerfile` và `docker-compose.yml` đảm bảo triển khai 1-click trên máy sạch.
- **Môi trường hoạt động:** `src/ecomreview/api/`, `src/ecomreview/ui/`, `docker/`.

---

## 6. `academic_researcher` (Nghiên Cứu Viên Khoa Học & Báo Cáo)
- **Vai trò:** Phụ trách chất lượng học thuật, biên soạn báo cáo 30–50 trang và slide bảo vệ.
- **Trách nhiệm chính:**
  - Khảo cứu 15–25 công trình học thuật liên quan đến ABSA và AI Agent.
  - Biên soạn cuốn chiếu 5 chương của báo cáo nghiên cứu.
  - Thực hiện phân tích lỗi Pareto (80/20) và case study thực tế Shop Áo Mưa.
  - Chuẩn bị slide bảo vệ (15–20 slide) và ngân hàng 30 câu hỏi phản biện.
- **Môi trường hoạt động:** `docs/report/`, `docs/`, `results/`.

<!-- CreBy: MenBoyBMN -->

