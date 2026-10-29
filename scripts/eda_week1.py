"""Script for exploratory data analysis (EDA) of raw and public review datasets."""

import csv
import json
from pathlib import Path

INTERIM_FILE = Path("data/interim/shop_reviews_anon.csv")
PUBLIC_FILE = Path("data/public/vlsp2018_absa_sample.json")
OUTPUT_MD = Path("docs/data_stats.md")


def analyze_dataset():
    """Compute statistics on available datasets and generate docs/data_stats.md."""
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)

    shop_count = 0
    shop_ratings = []
    shop_lengths = []

    if INTERIM_FILE.exists():
        with open(INTERIM_FILE, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                shop_count += 1
                if "rating" in row and row["rating"].strip().isdigit():
                    shop_ratings.append(int(row["rating"].strip()))
                text = row.get("text", "")
                shop_lengths.append(len(text.split()))

    public_count = 0
    if PUBLIC_FILE.exists():
        with open(PUBLIC_FILE, mode="r", encoding="utf-8") as f:
            data = json.load(f)
            public_count = len(data)

    avg_shop_len = sum(shop_lengths) / len(shop_lengths) if shop_lengths else 0.0
    avg_rating = sum(shop_ratings) / len(shop_ratings) if shop_ratings else 0.0

    lines = [
        "# Báo Cáo Thống Kê Khám Phá Dữ Liệu (Exploratory Data Analysis - EDA)",
        "",
        "> **Cập nhật lần cuối:** Tuần 1",
        "> **Trạng thái:** Track 1 (Public Benchmark) + Track 2 (Shop Áo Mưa)",
        "",
        "---",
        "",
        "## 1. Tổng Quan Cỡ Mẫu (Sample Overview)",
        "",
        "| Tập Dữ Liệu | Nguồn | Số Mẫu | Định Dạng | Trạng Thái PII |",
        "| :--- | :--- | :--- | :--- | :--- |",
        f"| **Track 1: Public Benchmark** | VLSP / UIT-ViSFD | {public_count} mẫu | "
        "JSON (`data/public/`) | Công khai, không có PII |",
        f"| **Track 2: Shop Áo Mưa** | Shopee / TikTok Shop | {shop_count} mẫu | "
        "CSV (`data/interim/`) | Đã khử khuẩn PII bằng Regex |",
        "",
        "---",
        "",
        "## 2. Đặc Trưng Dữ Liệu Shop Áo Mưa (Track 2)",
        "",
        f"- **Tổng số mẫu:** {shop_count} phản hồi.",
        f"- **Độ dài trung bình (số từ):** {avg_shop_len:.1f} từ/phản hồi.",
        "- **Phân bố số sao (Rating):**",
        f"  - Số lượng mẫu có rating: {len(shop_ratings)}",
        f"  - Điểm rating trung bình: {avg_rating:.2f} / 5.0",
        "",
        "> [!NOTE]",
        "> Khi bạn bổ sung thêm dữ liệu vào `data/raw/shop_reviews_raw.csv`, "
        "hãy chạy lại script `python scripts/anonymize_shop_data.py` và "
        "`python scripts/eda_week1.py` để cập nhật bảng thống kê tự động.",
        "",
        "<!-- CreBy: MenBoyBMN -->",
        "",
    ]

    with open(OUTPUT_MD, mode="w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[+] EDA report generated at: {OUTPUT_MD}")


if __name__ == "__main__":
    analyze_dataset()

# CreBy: MenBoyBMN
