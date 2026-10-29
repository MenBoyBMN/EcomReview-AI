# EcomReview AI

> Hệ thống AI Agent tự động phân tích phản hồi khách hàng tiếng Việt (ABSA) và đề xuất kế hoạch hành động marketing / tối ưu sản phẩm khả thi cho doanh nghiệp vừa và nhỏ (SMEs).

---

## 1. Giới Thiệu

EcomReview AI là đề tài kết hợp giữa nghiên cứu khoa học học thuật (chuẩn báo cáo 30–50 trang, 3 baselines so sánh với Gemini Flash, kiểm định Bootstrap CI 95%) và sản phẩm công nghệ thực tế (FastAPI, PostgreSQL 16, Streamlit Dashboard 4 trang, Docker Compose 1-click).

Case study trọng tâm: Ngành hàng **Áo mưa thời trang & tiện lợi** trên các sàn TMĐT **Shopee** và **TikTok Shop**.

---

## 2. Ngăn Xếp Công Nghệ (Tech Stack)

- **Ngôn ngữ:** Python 3.11+
- **AI / LLM:** Google Gemini Flash (`google-genai`), Pydantic v2 Structured Output
- **NLP / ML Baselines:** Rule Lexicon, TF-IDF + Logistic Regression, Pretrained ViSoBERT (`uitnlp/visobert`)
- **Cơ sở dữ liệu:** PostgreSQL 16
- **Backend API:** FastAPI, Uvicorn
- **Frontend UI:** Streamlit đa trang, Plotly
- **Đóng gói & Kiểm thử:** Pytest, Ruff, Docker Compose

---

## 3. Cấu Trúc Thư Mục Chuẩn

```text
ecomreview/
├── data/
│   ├── raw/                  # Dữ liệu gốc Shopee/TikTok (không commit git)
│   ├── public/               # Benchmark công khai (UIT-ViSFD / VLSP)
│   ├── interim/              # Dữ liệu đã làm sạch & khử khuẩn PII
│   ├── gold/                 # Tập dev.jsonl, test_locked.jsonl
│   └── cache/                # Cache phản hồi Gemini theo SHA-256
├── docs/
│   ├── scope.md              # Phạm vi, 3 RQ, giả thuyết nghiên cứu
│   ├── annotation_guideline.md # Hướng dẫn gán nhãn 8 khía cạnh
│   ├── data_stats.md         # Thống kê khám phá dữ liệu (EDA)
│   └── report/               # Bản thảo báo cáo 5 chương (30–50 trang)
├── knowledge/                # Tri thức miền ngành hàng (Playbook)
├── models/                   # Checkpoints mô hình B2, B3
├── prompts/                  # Quản lý phiên bản Prompt
├── results/                  # Kết quả RQ1, RQ2, RQ3, trace logs
├── scripts/                  # Scripts tiền xử lý, gán nhãn, xuất báo cáo
├── src/ecomreview/
│   ├── schemas.py            # Pydantic data contracts
│   ├── security.py           # Bộ lọc Prompt Injection & ẩn danh PII
│   ├── normalize.py          # Chuẩn hóa tiếng Việt mạng xã hội (Tuần 2)
│   ├── db/                   # Kết nối & truy vấn PostgreSQL (Tuần 5)
│   ├── analyze/              # B1 (Rule), B2 (TF-IDF), B3 (ViSoBERT), A1 (Gemini)
│   ├── agent/                # StateGraph, Aggregator, Planner, Critic
│   ├── api/                  # FastAPI router & services
│   ├── ui/                   # Streamlit Dashboard (4 trang)
│   └── eval/                 # Bootstrap CI, Metrics, Groundedness check
├── tests/                    # Unit tests & Integration tests
├── docker/                   # Dockerfile cho api và ui
├── docker-compose.yml        # Điều phối 3 services
├── pyproject.toml            # Cấu hình pythonpath, pytest, ruff
├── requirements.txt          # Danh sách thư viện phụ thuộc
└── README.md
```

---

## 4. Tiến Độ Thực Hiện (Project Milestones)

- [x] **Tuần 1: Khung đề tài, Khảo sát dữ liệu (EDA) & Phòng thủ 4 lớp Prompt Injection**
  - Đặc tả phạm vi nghiên cứu 3 câu hỏi (RQ1–RQ3), 3 giả thuyết (H1–H3) tại [`docs/scope.md`](docs/scope.md).
  - Thu thập 245 đánh giá thô, làm sạch PII và phân tích phân phối tại [`docs/data_stats.md`](docs/data_stats.md).
  - Hợp đồng dữ liệu chuẩn mực Pydantic v2 [`schemas.py`](src/ecomreview/schemas.py) & Lớp bảo mật [`security.py`](src/ecomreview/security.py).
- [x] **Tuần 2: Chuẩn hóa tiếng Việt mạng xã hội, Quy chuẩn gán nhãn & Khóa băm SHA-256**
  - Bộ tiền xử lý Teencode, Emoji, biến thể ký tự [`normalize.py`](src/ecomreview/normalize.py).
  - Taxonomy 8 khía cạnh ngành áo mưa và cẩm nang gán nhãn [`annotation_guideline.md`](docs/annotation_guideline.md).
  - Phân chia kiến trúc dữ liệu kép (Benchmark 2.200 mẫu & Shop 165 mẫu) và khóa SHA-256 tại [`docs/datasets_and_split.md`](docs/datasets_and_split.md).
- [x] **Tuần 3: Baselines (B1, B2), Mô hình đề xuất A1 (Gemini Flash), Bootstrap CI & Cohen's Kappa**
  - Động cơ đánh giá Bootstrap 95% CI ($B=2.000$) & Paired Bootstrap Test tại [`metrics.py`](src/ecomreview/eval/metrics.py).
  - Triển khai Baseline B1 (Rule-based Lexicon) và Baseline B2 (Two-Tier TF-IDF + Logistic Regression).
  - Triển khai Analyzer A1 (Gemini Flash Structured Output) kèm bộ nhớ đệm SHA-256 và Quota Circuit-Breaker.
  - Kiểm định độ tin cậy gán nhãn Intra-Annotator Cohen's Kappa $\kappa = 0,5288$ tại [`docs/kappa_report.md`](docs/kappa_report.md) và xuất bản 125 mẫu vàng [`data/gold/gold_v2.jsonl`](data/gold/gold_v2.jsonl).
  - Hoàn thiện bản thảo Chương 3 Báo cáo học thuật tại [`docs/report/ch3_methodology.md`](docs/report/ch3_methodology.md).
- [ ] **Tuần 4: Baseline B3 (Fine-tuning ViSoBERT Colab T4), Ablation Study (RQ2) & Chốt RQ1/RQ2**
- [ ] **Tuần 5–7: Tác tử State-Graph thuần, Bộ lập kế hoạch (Action Planner) & Thẩm định lai (Hybrid Critic)**
- [ ] **Tuần 8–10: FastAPI Backend, Streamlit Dashboard 4 trang, Đóng gói Docker Compose 1-click & Video Demo**

---

## 5. Kết Quả Thực Nghiệm Ban Đầu (Dev Set Benchmark)

Kết quả so sánh giữa các phương pháp trên tập phát triển (`dev.jsonl` - 60 mẫu) với khoảng tin cậy Bootstrap 95% ($B=2.000$):

| Hệ Thống (Model) | Overall Sentiment Macro-F1 | Aspect Detection F1 | ABSA Macro-F1 (Aspect + Polarity) | Quote Fidelity | Độ Trễ (Latency) | Chi Phí (Cost / 1k) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **B1: Rule & Lexicon** | 0.4801 [0.3962 - 0.7851] | 0.8664 | 0.5113 [0.4556 - 0.5573] | 98.1% | 0.5 ms | $0.00 |
| **B2: TF-IDF + LogReg** | 0.4914 [0.4081 - 0.7980] | 0.9969 | 0.9978 [0.9915 - 1.0000] | 100.0% | 19.3 ms | $0.00 |
| **A1: Gemini Flash (v1)** | 0.4855 [0.4036 - 0.7962] | 0.8664 | 0.5087 [0.4519 - 0.5539] | 98.1% | 24.7 ms | $0.05 |

---

## 6. Hướng Dẫn Cài Đặt & Vận Hành Nhanh

```powershell
# 1. Kích hoạt môi trường ảo Python
.\.venv\Scripts\Activate.ps1

# 2. Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt

# 3. Chạy toàn bộ 39 bài unit & integration test
pytest -v

# 4. Kiểm tra chuẩn hóa định dạng và chất lượng mã nguồn
ruff check .
ruff format . --check

# 5. Tái lập thực nghiệm so sánh Baselines trên tập Dev
python scripts/evaluate_dev.py

# 6. Tính toán hệ số tin cậy gán nhãn Cohen's Kappa
python scripts/calculate_kappa.py
```

<!-- CreBy: MenBoyBMN -->

