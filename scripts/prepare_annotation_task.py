"""Prepare annotation template and pre-annotations for the 125 real shop reviews.

Assists the researcher in completing Task 2.3 (Human Annotation Round 1) with maximum speed,
providing rule-based suggestions while leaving final judgment to the human annotator.
"""

import json
from pathlib import Path

import pandas as pd

from ecomreview.schemas import Aspect, Polarity

INTERIM_CSV = Path("data/interim/shop_reviews_anon.csv")
GOLD_DIR = Path("data/gold")

# Simple rule dictionary for domain aspect hints
ASPECT_HINTS: list[tuple[str, Aspect, list[str]]] = [
    ("chống thấm", Aspect.WATERPROOF, ["chống thấm", "ngấm", "ướt", "nước"]),
    (
        "chất liệu",
        Aspect.MATERIAL_DURABILITY,
        ["vải", "da cá", "dày", "mỏng", "rách", "khóa", "cúc", "bền"],
    ),
    (
        "kích thước",
        Aspect.FIT_SIZE,
        ["size", "sz", "vừa", "rộng", "chật", "dài", "ngắn", "cao", "kg", "m"],
    ),
    (
        "tiện dụng",
        Aspect.COMFORT_USABILITY,
        ["tiện", "gấp", "kính", "bí", "mát", "nóng", "cổ", "tay"],
    ),
    ("giá cả", Aspect.PRICE_VALUE, ["giá", "tiền", "đắt", "rẻ", "đáng"]),
    ("vận chuyển", Aspect.PACKAGING_SHIPPING, ["giao", "ship", "đóng gói", "hộp", "túi"]),
    (
        "chăm sóc khách hàng",
        Aspect.CUSTOMER_SERVICE,
        ["tư vấn", "shop", "trả lời", "đổi", "nhiệt tình"],
    ),
    (
        "thiết kế thẩm mỹ",
        Aspect.ACCESSIBILITY_DESIGN,
        ["màu", "đẹp", "xấu", "mẫu", "kiểu", "thời trang"],
    ),
]


def suggest_opinions(text: str, rating: int) -> tuple[list[dict], str, bool]:
    """Suggest candidate opinions and polarity based on keywords and rating."""
    lower_t = text.lower()
    opinions = []

    # Polarity heuristic from rating
    default_pol = Polarity.POS if rating >= 4 else (Polarity.NEG if rating <= 2 else Polarity.NEU)

    for _, aspect, keywords in ASPECT_HINTS:
        matched_kw = [kw for kw in keywords if kw in lower_t]
        if matched_kw:
            # Check negative polarity cues around the keyword
            neg_cues = ["không", "ko", "k", "kém", "chán", "tệ", "thất vọng", "rách", "ướt", "ngấm"]
            is_neg = any(nc in lower_t for nc in neg_cues) and default_pol == Polarity.NEG
            pol = Polarity.NEG if is_neg else default_pol

            opinions.append(
                {
                    "aspect": aspect.value,
                    "polarity": pol.value,
                    "evidence": matched_kw[0],
                }
            )

    if not opinions and len(text.split()) > 3:
        opinions.append(
            {
                "aspect": Aspect.GENERAL.value,
                "polarity": default_pol.value,
                "evidence": text[:20],
            }
        )

    is_informative = len(text.split()) >= 3 and any(c.isalnum() for c in text)
    overall_sent = default_pol.value

    return opinions, overall_sent, is_informative


def prepare_template():
    """Extract 125 non-empty reviews and generate CSV + Excel annotation templates."""
    if not INTERIM_CSV.exists():
        raise FileNotFoundError(f"Missing interim CSV at {INTERIM_CSV}")

    df = pd.read_csv(INTERIM_CSV)
    df = df.dropna(subset=["text"])
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"] != ""]

    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    starter_jsonl_records = []

    for _, row in df.iterrows():
        rev_id = row["review_id"]
        text = row["text"]
        rating = int(row["rating"]) if pd.notna(row["rating"]) else 5

        suggested_ops, overall_sent, informative = suggest_opinions(text, rating)

        # Compact string format: "WATERPROOF#positive#chống nước; FIT_SIZE#positive#vừa vặn"
        opinions_compact = "; ".join(
            f"{op['aspect']}#{op['polarity']}#{op['evidence']}" for op in suggested_ops
        )

        rows.append(
            {
                "review_id": rev_id,
                "rating": rating,
                "text": text,
                "overall_sentiment": overall_sent,
                "opinions": opinions_compact,
                "informative": 1 if informative else 0,
                "annotator_notes": "",
            }
        )

        starter_jsonl_records.append(
            {
                "id": rev_id,
                "text": text,
                "source_type": "real_shop",
                "rating": rating,
                "opinions": suggested_ops,
                "overall_sentiment": overall_sent,
                "informative": informative,
            }
        )

    df_out = pd.DataFrame(rows)

    # Save CSV template
    csv_path = GOLD_DIR / "annotation_template_125_real.csv"
    df_out.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"[+] Saved annotation CSV template: {csv_path} ({len(df_out)} reviews)")

    # Save Excel template for easy human editing
    xlsx_path = GOLD_DIR / "annotation_template_125_real.xlsx"
    df_out.to_excel(xlsx_path, index=False)
    print(f"[+] Saved annotation Excel template: {xlsx_path}")

    # Save starter JSONL for immediate baseline or review
    starter_jsonl_path = GOLD_DIR / "gold_round1.jsonl"
    with open(starter_jsonl_path, "w", encoding="utf-8") as f:
        for rec in starter_jsonl_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[+] Initial gold_round1.jsonl created: {starter_jsonl_path}")


if __name__ == "__main__":
    prepare_template()

# CreBy: MenBoyBMN
