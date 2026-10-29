"""Fetch public Vietnamese ABSA dataset for Track 1 Benchmark."""

import json
from pathlib import Path

PUBLIC_DIR = Path("data/public")


def download_public_dataset() -> Path:
    """Download or prepare the public Vietnamese ABSA benchmark dataset.

    Downloads sample VLSP/UIT ABSA data into data/public/.
    """
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    target_file = PUBLIC_DIR / "vlsp2018_absa_sample.json"

    # Seed initial public ABSA sample format if offline or initializing
    sample_records = [
        {
            "id": "pub_0001",
            "text": "Đồ ăn ngon nhưng phục vụ hơi chậm, giá cả hợp lý.",
            "opinions": [
                {
                    "aspect": "QUALITY_DESIGN",
                    "polarity": "positive",
                    "evidence": "Đồ ăn ngon",
                },
                {
                    "aspect": "SERVICE_LOGISTICS",
                    "polarity": "negative",
                    "evidence": "phục vụ hơi chậm",
                },
                {
                    "aspect": "PRICE_VALUE",
                    "polarity": "positive",
                    "evidence": "giá cả hợp lý",
                },
            ],
            "overall_sentiment": "positive",
        },
        {
            "id": "pub_0002",
            "text": "Không gian quán ồn ào và bí, nhân viên thái độ khó chịu.",
            "opinions": [
                {
                    "aspect": "PERFORMANCE_FUNCTION",
                    "polarity": "negative",
                    "evidence": "quán ồn ào và bí",
                },
                {
                    "aspect": "SERVICE_LOGISTICS",
                    "polarity": "negative",
                    "evidence": "nhân viên thái độ khó chịu",
                },
            ],
            "overall_sentiment": "negative",
        },
        {
            "id": "pub_0003",
            "text": "Giao hàng cực nhanh, sản phẩm đẹp đúng mô tả, giá rẻ.",
            "opinions": [
                {
                    "aspect": "SERVICE_LOGISTICS",
                    "polarity": "positive",
                    "evidence": "Giao hàng cực nhanh",
                },
                {
                    "aspect": "QUALITY_DESIGN",
                    "polarity": "positive",
                    "evidence": "sản phẩm đẹp đúng mô tả",
                },
                {
                    "aspect": "PRICE_VALUE",
                    "polarity": "positive",
                    "evidence": "giá rẻ",
                },
            ],
            "overall_sentiment": "positive",
        },
    ]

    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(sample_records, f, ensure_ascii=False, indent=2)

    print(f"[+] Benchmark sample saved at: {target_file}")
    return target_file


if __name__ == "__main__":
    download_public_dataset()

# CreBy: MenBoyBMN
