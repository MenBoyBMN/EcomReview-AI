"""Process gold annotations, split into dev/test_locked, and compute SHA-256 lock.

Implements Task 2.4: Group-aware data split and cryptographic lock against test leakage.
- dev.jsonl: 20 real shop reviews + 40 synthetic_dev reviews = 60 samples
- test_locked.jsonl: 105 real shop reviews (100% real reviews)
- Guaranteed 0 text overlap and 0 ID overlap (Strict anti-leakage).
"""

import hashlib
import json
import random
from pathlib import Path

import pandas as pd

GOLD_DIR = Path("data/gold")
DOCS_DIR = Path("docs")
REAL_GOLD_JSONL = GOLD_DIR / "gold_round1.jsonl"
SYN_DEV_JSONL = GOLD_DIR / "synthetic_dev.jsonl"
DEV_JSONL = GOLD_DIR / "dev.jsonl"
TEST_LOCKED_JSONL = GOLD_DIR / "test_locked.jsonl"
SPLIT_DOC = DOCS_DIR / "datasets_and_split.md"


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def process_and_lock_splits():
    """Split gold reviews into dev and test_locked, verify zero leakage, and compute hash."""
    if not REAL_GOLD_JSONL.exists():
        raise FileNotFoundError(f"Missing real gold data at {REAL_GOLD_JSONL}")
    if not SYN_DEV_JSONL.exists():
        raise FileNotFoundError(f"Missing synthetic dev data at {SYN_DEV_JSONL}")

    # Load real reviews
    real_records = []
    with open(REAL_GOLD_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                real_records.append(json.loads(line))

    # Load synthetic dev reviews
    syn_records = []
    with open(SYN_DEV_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                syn_records.append(json.loads(line))

    # Group-based split by text to prevent identical reviews appearing in both dev and test
    df_real = pd.DataFrame(real_records)
    df_real["text_norm"] = df_real["text"].str.strip().str.lower()

    # Group by text_norm
    grouped = df_real.groupby("text_norm")
    text_groups = [group for _, group in grouped]

    # Deterministic shuffle of groups using fixed seed=42
    rng = random.Random(42)
    rng.shuffle(text_groups)

    dev_real_groups = []
    test_real_groups = []
    accumulated_dev_count = 0

    for grp in text_groups:
        if accumulated_dev_count + len(grp) <= 20:
            dev_real_groups.append(grp)
            accumulated_dev_count += len(grp)
        else:
            test_real_groups.append(grp)

    # If count is slightly under 20 due to group sizes, fill remainder from single-occurrence items
    if accumulated_dev_count < 20:
        for i, grp in enumerate(test_real_groups):
            if len(grp) == 1 and accumulated_dev_count < 20:
                dev_real_groups.append(grp)
                test_real_groups.pop(i)
                accumulated_dev_count += 1
                if accumulated_dev_count == 20:
                    break

    df_real_dev = pd.concat(dev_real_groups, ignore_index=True)
    df_real_test = pd.concat(test_real_groups, ignore_index=True)

    # Sample 40 synthetic reviews for dev (with fixed seed=42)
    df_syn = pd.DataFrame(syn_records)
    df_syn_dev = df_syn.sample(n=40, random_state=42)

    # Clean intermediate text_norm column before saving
    df_real_dev = df_real_dev.drop(columns=["text_norm"])
    df_real_test = df_real_test.drop(columns=["text_norm"])

    # Combine dev samples (20 real + 40 synthetic = 60 total)
    df_dev = pd.concat([df_real_dev, df_syn_dev], ignore_index=True)

    # Save dev.jsonl
    with open(DEV_JSONL, "w", encoding="utf-8") as f:
        for item in df_dev.to_dict(orient="records"):
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"[+] Saved dev.jsonl: {len(df_dev)} records (20 real + 40 synthetic)")

    # Save test_locked.jsonl
    with open(TEST_LOCKED_JSONL, "w", encoding="utf-8") as f:
        for item in df_real_test.to_dict(orient="records"):
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"[+] Saved test_locked.jsonl: {len(df_real_test)} records (100% real shop reviews)")

    # Verification: zero overlap between dev and test_locked on both ID and text
    dev_texts = set(df_dev["text"].str.strip().str.lower())
    test_texts = set(df_real_test["text"].str.strip().str.lower())
    dev_ids = set(df_dev["id"])
    test_ids = set(df_real_test["id"])

    overlap_ids = dev_ids.intersection(test_ids)
    overlap_texts = dev_texts.intersection(test_texts)

    assert len(overlap_ids) == 0, f"DATA LEAKAGE: ID overlap detected: {overlap_ids}"
    assert len(overlap_texts) == 0, f"DATA LEAKAGE: Text overlap detected: {overlap_texts}"
    print("[+] Zero-leakage verification PASSED: 0 text overlap and 0 ID overlap!")

    # Compute SHA-256 hashes
    test_hash = compute_sha256(TEST_LOCKED_JSONL)
    dev_hash = compute_sha256(DEV_JSONL)
    pub_test_hash = compute_sha256(Path("data/public/test.jsonl"))

    print(f"[+] SHA-256 of test_locked.jsonl: {test_hash}")

    # Generate / update docs/datasets_and_split.md
    doc_lines = [
        "# Biên Bản Chia Tập Dữ Liệu & Khóa Mã Băm SHA-256 (Data Split & Lock Protocol)",
        "",
        "> **Mục tiêu:** Chống rò rỉ dữ liệu và đảm bảo tính liêm chính khoa học cho ABSA.",
        "> **Trạng thái:** Đã khóa tập kiểm thử (Test Locked) · Tuần 2",
        "",
        "---",
        "",
        "## 1. Kiến Trúc Dữ Liệu Kép (Dual-Track Architecture)",
        "",
        "Hệ thống **EcomReview AI** vận hành trên 2 luồng dữ liệu độc lập:",
        "",
        "| Luồng | Tập Dữ Liệu | Nguồn Gốc | Tổng Mẫu | Mục Đích Sử Dụng |",
        "| :--- | :--- | :--- | :---: | :--- |",
        "| **Track 1: Public Benchmark** | UIT-ViSFD (Normalized) | TMĐT Điện Thoại | 2.200 | "
        "Huấn luyện Baseline B2, B3 và đo chuyển miền (RQ2). |",
        "| **Track 2: Shop Thật** | TikTok Shop Áo Mưa | Shop thực tế (Shop A) | 125 | "
        "Đánh giá thích ứng miền và chạy AI Agent (RQ1, RQ3). |",
        "",
        "---",
        "",
        "## 2. Chi Tiết Phân Chia Tập Dữ Liệu",
        "",
        "### 2.1. Track 1 — Public Benchmark (`data/public/`)",
        "- `train.jsonl`: 1.500 mẫu (dùng huấn luyện mô hình học máy và fine-tuning).",
        "- `val.jsonl`: 300 mẫu (dùng chọn epoch và hyperparameter).",
        "- `test.jsonl`: 400 mẫu phân tầng (dùng so sánh 4 mô hình: B1, B2, B3, A1).",
        "",
        "### 2.2. Track 2 — Shop Áo Mưa (`data/gold/`)",
        "- **Tập Phát Triển (`dev.jsonl` - 60 mẫu):**",
        "  - **20 mẫu thật (`real_shop`):** Chia theo nhóm nội dung (Group-based split),",
        "    đảm bảo không trùng lặp câu chữ với tập test.",
        "  - **40 mẫu giả lập (`synthetic_dev`):** Gồm teencode, không dấu, emoji, mỉa mai.",
        "  - *Mục đích:* Dùng để chọn few-shot, tinh chỉnh prompt và hiệu chỉnh ngưỡng.",
        "- **Tập Kiểm Thử Khóa (`test_locked.jsonl` - 105 mẫu):**",
        "  - **105 mẫu thực tế 100% từ shop áo mưa.**",
        "  - **0% mẫu synthetic** (tuyệt đối không trộn mẫu nhân tạo vào tập test).",
        "  - *Quy tắc:* Khóa chặt bằng SHA-256, không nhìn lỗi để sửa prompt.",
        "",
        "---",
        "",
        "## 3. Khóa Bảo Mật SHA-256 & Bằng Chứng Liêm Chính",
        "",
        "| Tệp Dữ Liệu | Số Dòng | Định Dạng | Mã Băm SHA-256 |",
        "| :--- | :---: | :---: | :--- |",
        f"| `data/gold/test_locked.jsonl` | 105 | JSONL | `{test_hash}` |",
        f"| `data/gold/dev.jsonl` | 60 | JSONL | `{dev_hash}` |",
        f"| `data/public/test.jsonl` | 400 | JSONL | `{pub_test_hash}` |",
        "",
        "### Kiểm tra rò rỉ (Leakage Audit Verification):",
        "- Giao tập ID giữa `dev` và `test_locked`: **0 mẫu (Passed)**.",
        "- Giao tập Text chuẩn hóa giữa `dev` và `test_locked`: **0 mẫu (Passed)**.",
        "- Phương pháp phân chia: **Group-aware text splitting** (cố định `seed=42`).",
        "",
        "<!-- CreBy: MenBoyBMN -->",
        "",
    ]
    with open(SPLIT_DOC, "w", encoding="utf-8") as f:
        f.write("\n".join(doc_lines))
    print(f"[+] Protocol document updated at: {SPLIT_DOC}")


if __name__ == "__main__":
    process_and_lock_splits()

# CreBy: MenBoyBMN
