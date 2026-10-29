"""Script to anonymize raw customer reviews and scrub PII."""

import csv
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows terminal
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure src is in python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ecomreview.security import scrub_pii

# Default paths
RAW_FILE = Path("data/raw/shop_reviews_raw.csv")
INTERIM_FILE = Path("data/interim/shop_reviews_anon.csv")


def anonymize_dataset(raw_path: Path = RAW_FILE, output_path: Path = INTERIM_FILE) -> int:
    """Read raw review CSV, remove PII, anonymize order_id, and write to interim folder.

    Expected columns in raw CSV:
    review_id, platform, shop, product, rating, text, has_media, created_at, source, order_id
    """
    if not raw_path.exists():
        print(f"[!] File not found: {raw_path}")
        print("    Please place your shop reviews CSV at data/raw/shop_reviews_raw.csv first.")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0

    with (
        open(raw_path, mode="r", encoding="utf-8-sig") as infile,
        open(output_path, mode="w", encoding="utf-8", newline="") as outfile,
    ):
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            print("[!] CSV has no header.")
            return 0

        # Remove direct PII fields like username, customer_name, and raw sku_id
        ignored_fields = {"user", "username", "customer_name", "sku_id"}
        target_fields = [f for f in reader.fieldnames if f.lower() not in ignored_fields]
        writer = csv.DictWriter(outfile, fieldnames=target_fields)
        writer.writeheader()

        for idx, row in enumerate(reader, start=1):
            cleaned_row = {k: v for k, v in row.items() if k in target_fields}
            # Mask order_id with synthetic ordinal ID to protect real e-commerce order numbers
            if "order_id" in cleaned_row:
                cleaned_row["order_id"] = f"ord_{idx:04d}" if cleaned_row["order_id"] else ""

            if "text" in cleaned_row and cleaned_row["text"]:
                cleaned_row["text"] = scrub_pii(cleaned_row["text"])
            writer.writerow(cleaned_row)
            count += 1

    print(f"[+] Successfully anonymized {count} reviews -> {output_path}")
    return count


if __name__ == "__main__":
    raw_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else RAW_FILE
    out_arg = Path(sys.argv[2]) if len(sys.argv) > 2 else INTERIM_FILE
    anonymize_dataset(raw_arg, out_arg)

# CreBy: MenBoyBMN
