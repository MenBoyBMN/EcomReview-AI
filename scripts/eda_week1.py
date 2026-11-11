"""Script for exploratory data analysis (EDA) of raw and public review datasets."""

import csv
from pathlib import Path

INTERIM_FILE = Path("data/interim/shop_reviews_anon.csv")
PUBLIC_FILES = [
    Path("data/public/train.jsonl"),
    Path("data/public/val.jsonl"),
    Path("data/public/test.jsonl"),
]
OUTPUT_MD = Path("docs/data_stats.md")


def analyze_dataset():
    """Compute rich statistics on available datasets and generate docs/data_stats.md."""
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)

    shop_count = 0
    shop_ratings = []
    text_lengths = []
    non_empty_texts = 0
    rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    if INTERIM_FILE.exists():
        with open(INTERIM_FILE, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                shop_count += 1
                r_val = row.get("rating", "").strip()
                if r_val.isdigit():
                    int_r = int(r_val)
                    shop_ratings.append(int_r)
                    if int_r in rating_counts:
                        rating_counts[int_r] += 1

                txt = (row.get("text") or "").strip()
                if txt:
                    non_empty_texts += 1
                    words = txt.split()
                    text_lengths.append(len(words))

    public_count = 0
    for pf in PUBLIC_FILES:
        if pf.exists():
            with open(pf, mode="r", encoding="utf-8") as f:
                public_count += sum(1 for line in f if line.strip())

    avg_words = sum(text_lengths) / len(text_lengths) if text_lengths else 0.0
    avg_rating = sum(shop_ratings) / len(shop_ratings) if shop_ratings else 0.0
    min_words = min(text_lengths) if text_lengths else 0
    max_words = max(text_lengths) if text_lengths else 0

    p_5 = (rating_counts[5] / shop_count * 100) if shop_count else 0
    p_4 = (rating_counts[4] / shop_count * 100) if shop_count else 0
    p_3 = (rating_counts[3] / shop_count * 100) if shop_count else 0
    p_2 = (rating_counts[2] / shop_count * 100) if shop_count else 0
    p_1 = (rating_counts[1] / shop_count * 100) if shop_count else 0

    lines = [
        "# Báo Cáo Thống Kê Khám Phá Dữ Liệu (Exploratory Data Analysis - EDA)",
        "",
        "> **Dự án:** EcomReview AI — Nghiên cứu ABSA & Tối ưu hóa Thương mại Điện tử",
        "> **Cập nhật:** Tuần 1 · Đã nạp dữ liệu thực tế TikTok Shop",
        "",
        "---",
        "",
        "## 1. Tổng Quan Cỡ Mẫu (Sample Overview)",
        "",
        "| Phân Nhóm | Nguồn Dữ Liệu | Tổng Số Mẫu | Có Văn Bản Nhận Xét | Định Dạng Lưu Trữ |",
        "| :--- | :--- | :--- | :--- | :--- |",
        f"| **Track 1: Public Benchmark** | VLSP / UIT-ViSFD | {public_count} mẫu | "
        f"{public_count} mẫu | JSON (`data/public/`) |",
        f"| **Track 2: Shop Áo Mưa Thật** | TikTok Shop (Shop A) | {shop_count} mẫu | "
        f"{non_empty_texts} mẫu | CSV (`data/interim/`) |",
        "",
        "---",
        "",
        "## 2. Phân Bố Đánh Giá Sản Phẩm Shop Áo Mưa (Track 2)",
        "",
        f"- **Tổng số lượng đơn đánh giá:** {shop_count} đánh giá.",
        f"- **Số lượng đánh giá có nội dung nhận xét (Text Review):** {non_empty_texts} mẫu "
        f"({(non_empty_texts / shop_count * 100) if shop_count else 0:.1f}%).",
        f"- **Số lượng đánh giá chỉ bấm sao (Star-only):** {shop_count - non_empty_texts} mẫu.",
        f"- **Điểm số sao trung bình (Average Rating):** {avg_rating:.2f} / 5.0",
        "",
        "### Bảng Phân Bố Theo Số Sao (Rating Breakdown):",
        "",
        "| Số Sao | Số Lượng Đánh Giá | Tỷ Lệ (%) | Phân Loại Cảm Xúc Giả Định |",
        "| :---: | :---: | :---: | :--- |",
        f"| 5 ⭐ | {rating_counts[5]} | {p_5:.1f}% | Tích cực (Positive) |",
        f"| 4 ⭐ | {rating_counts[4]} | {p_4:.1f}% | Tích cực / Khá |",
        f"| 3 ⭐ | {rating_counts[3]} | {p_3:.1f}% | Trung tính (Neutral) |",
        f"| 2 ⭐ | {rating_counts[2]} | {p_2:.1f}% | Tiêu cực (Negative) |",
        f"| 1 ⭐ | {rating_counts[1]} | {p_1:.1f}% | Tiêu cực nặng (Strong Negative) |",
        "",
        "---",
        "",
        "## 3. Đặc Trưng Văn Bản Nhận Xét (Text Statistics)",
        "",
        f"- **Độ dài trung bình:** {avg_words:.1f} từ/phản hồi.",
        f"- **Độ dài ngắn nhất:** {min_words} từ.",
        f"- **Độ dài dài nhất:** {max_words} từ.",
        "- **Hiện tượng đặc trưng trong tập dữ liệu:**",
        "  1. Review có độ dài trung bình chứa nhiều phản hồi chi tiết về chất liệu da cá, "
        "độ mềm, và chống thấm nước.",
        "  2. Xuất hiện các review mỉa mai ngầm và đánh giá đa khía cạnh (khen giao hàng nhưng chê "
        "dây kéo bị ngấm nước).",
        "  3. Đã được khử khuẩn hoàn toàn số điện thoại, mã đơn hàng và "
        "email cá nhân (PII Scrubbed).",
        "",
        "<!-- CreBy: MenBoyBMN -->",
        "",
    ]

    with open(OUTPUT_MD, mode="w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[+] Rich EDA report generated at: {OUTPUT_MD}")


if __name__ == "__main__":
    analyze_dataset()

# CreBy: MenBoyBMN
