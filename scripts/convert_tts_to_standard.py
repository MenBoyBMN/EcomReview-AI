"""Convert raw TikTok Shop (TTS) exported review CSV to standard schema.

Target Schema:
review_id, platform, shop, product, rating, text, has_media, created_at, source, order_id, sku_id
"""

import csv
import sys
from pathlib import Path

INPUT_FILE = Path("data/raw/20261029_tts_reviews.csv")
OUTPUT_RAW = Path("data/raw/shop_reviews_raw.csv")


def convert_tts_to_standard(
    input_path: Path = INPUT_FILE,
    output_path: Path = OUTPUT_RAW,
    shop_name: str = "shop_a",
    product_name: str = "Áo Mưa Da Cá",
) -> int:
    """Read TikTok Shop reviews CSV and convert to standardized format."""
    if not input_path.exists():
        print(f"[!] File not found: {input_path}")
        return 0

    rows_converted = 0
    with (
        open(input_path, mode="r", encoding="utf-8-sig") as infile,
        open(output_path, mode="w", encoding="utf-8", newline="") as outfile,
    ):
        reader = csv.DictReader(infile)
        fieldnames = [
            "review_id",
            "platform",
            "shop",
            "product",
            "rating",
            "text",
            "has_media",
            "created_at",
            "source",
            "order_id",
            "sku_id",
        ]
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for idx, row in enumerate(reader, start=1):
            review_id = f"tts_{idx:04d}"
            rating = row.get("rating", "").strip()
            raw_text = row.get("review_text", "") or ""
            # Clean up multi-line formatting without losing sentence separation
            clean_text = " ".join(raw_text.split())

            raw_date = row.get("review_date", "").strip()
            # Extract date portion YYYY-MM-DD
            created_at = raw_date.split()[0] if raw_date else ""

            writer.writerow(
                {
                    "review_id": review_id,
                    "platform": "tiktok",
                    "shop": shop_name,
                    "product": product_name,
                    "rating": rating,
                    "text": clean_text,
                    "has_media": "0",
                    "created_at": created_at,
                    "source": "review",
                    "order_id": row.get("order_id", "").strip(),
                    "sku_id": row.get("sku_id", "").strip(),
                }
            )
            rows_converted += 1

    print(f"[+] Converted {rows_converted} reviews to standard format: {output_path}")
    return rows_converted


if __name__ == "__main__":
    inp = Path(sys.argv[1]) if len(sys.argv) > 1 else INPUT_FILE
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT_RAW
    convert_tts_to_standard(inp, out)

# CreBy: MenBoyBMN
