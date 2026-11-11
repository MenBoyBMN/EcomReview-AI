"""Prepare annotation template and pre-annotations for the 125 real shop reviews.

Assists the researcher in completing Task 2.3 (Human Annotation Round 1) with maximum speed,
providing rule-based suggestions while leaving final judgment to the human annotator.
"""

import json
import re
from pathlib import Path

import pandas as pd

from ecomreview.schemas import Aspect, Polarity

INTERIM_CSV = Path("data/interim/shop_reviews_anon.csv")
GOLD_DIR = Path("data/gold")

# Refined rule dictionary for domain aspect hints (word-boundary safe)
ASPECT_HINTS: list[tuple[str, Aspect, list[str]]] = [
    (
        "chống thấm",
        Aspect.WATERPROOF,
        [
            "chống thấm",
            "chống nước",
            "ít bị thấm mưa",
            "không thấm",
            "bị thấm",
            "ngấm nước",
            "vô nước",
            "k lo ướt",
            "thấm",
            "ngấm",
            "ướt",
        ],
    ),
    (
        "chất liệu",
        Aspect.MATERIAL_DURABILITY,
        [
            "chất liệu",
            "da cá",
            "dày dặn",
            "độ dày",
            "nhựa mỏng",
            "dây kéo cứng cáp",
            "day kéo",
            "dây kéo",
            "bị lững",
            "vải",
            "dày",
            "mỏng",
            "rách",
            "khóa",
            "cúc",
            "bền",
        ],
    ),
    (
        "kích thước",
        Aspect.FIT_SIZE,
        [
            "kích thước",
            "size",
            "sz",
            "vừa vặn",
            "khá là vừa",
            "mặc rộng",
            "rộng",
            "chật",
            "cao 1m",
            "1m7",
            "95kg",
        ],
    ),
    (
        "tiện dụng",
        Aspect.COMFORT_USABILITY,
        [
            "thoải mái",
            "tiện lợi",
            "rất tiện",
            "nhanh gọn",
            "mặc êm",
            "tiện",
            "nhẹ",
            "gấp",
            "kính",
            "bí",
            "mát",
            "nóng",
        ],
    ),
    (
        "giá cả",
        Aspect.PRICE_VALUE,
        ["giá tiền", "túi tiền", "giá hợp lí", "giá hợp lý", "đáng tiền", "giá", "đắt", "rẻ"],
    ),
    (
        "vận chuyển",
        Aspect.PACKAGING_SHIPPING,
        ["giao hàng nhanh", "giao nhanh", "ship nhanh", "đóng gói", "ship", "hộp", "túi đựng"],
    ),
    (
        "chăm sóc khách hàng",
        Aspect.CUSTOMER_SERVICE,
        ["tư vấn", "trả lời", "đổi trả", "nhiệt tình"],
    ),
    (
        "thiết kế thẩm mỹ",
        Aspect.ACCESSIBILITY_DESIGN,
        ["màu chuẩn", "chuẩn màu", "đúng màu", "sai màu", "màu", "đẹp", "xấu", "thời trang"],
    ),
]


def _match_keyword(kw: str, lower_t: str) -> bool:
    """Match keyword safely using word boundaries for short tokens."""
    if kw == "vừa" and ("vừa phải" in lower_t or "vừa túi tiền" in lower_t or "vừa tiền" in lower_t):
        return False
    if len(kw) <= 4 and " " not in kw:
        return bool(re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", lower_t))
    return kw in lower_t


def suggest_opinions(text: str, rating: int) -> tuple[list[dict], str, bool]:
    """Suggest candidate opinions and polarity based on keywords and rating."""
    clean_t = text.strip()
    lower_t = clean_t.lower()
    opinions = []

    # Check non-informative or pure "ok" / symbol reviews
    stripped_alpha = re.sub(r"[^a-zA-ZÀ-ỹ0-9]+", " ", lower_t).strip()
    if stripped_alpha in ("", "ok", "oke", "okay", "đúng ảnh") or clean_t in ("✅", "👍"):
        return (
            [{"aspect": Aspect.GENERAL.value, "polarity": Polarity.NEU.value, "evidence": clean_t[:20] or "ok"}],
            Polarity.NEU.value,
            False,
        )
    if "djdefvhdgbjhdvj" in lower_t or lower_t == "nan":
        return [], Polarity.POS.value, False

    # Polarity heuristic from rating + strong content cues
    default_pol = Polarity.POS if rating >= 4 else (Polarity.NEG if rating <= 2 else Polarity.NEU)
    has_real_leak = ("bị thấm" in lower_t and "ít bị thấm" not in lower_t) or "vô nước" in lower_t
    if has_real_leak or any(
        p in lower_t
        for p in [
            "ko giao đúng kích thước",
            "không đúng mẫu",
            "ko giống mô tả",
            "bị lững",
            "rất thất vọng",
        ]
    ):
        default_pol = Polarity.NEG
    elif any(p in lower_t for p in ["chưa biết có bền", "chưa đc tốt lắm"]):
        default_pol = Polarity.NEU

    for _, aspect, keywords in ASPECT_HINTS:
        matched_kw = [kw for kw in keywords if _match_keyword(kw, lower_t)]
        if matched_kw:
            # Skip spurious ACCESSIBILITY_DESIGN if review is purely negative waterproof complaint with "đúng mẫu mã"
            if aspect == Aspect.ACCESSIBILITY_DESIGN and has_real_leak:
                continue

            pol = default_pol
            if aspect == Aspect.PACKAGING_SHIPPING and ("giao hàng nhanh" in lower_t or "giao nhanh" in lower_t):
                pol = Polarity.POS
            elif aspect == Aspect.MATERIAL_DURABILITY and (
                "nhựa mỏng" in lower_t or "chưa biết có bền" in lower_t or "chưa đc tốt lắm" in lower_t
            ):
                pol = Polarity.NEU
            elif aspect == Aspect.WATERPROOF and (
                "không thấm" in lower_t or "ít bị thấm" in lower_t or "k lo ướt" in lower_t or "chống thấm" in lower_t or "chống nước" in lower_t
            ):
                pol = Polarity.POS
            elif aspect == Aspect.WATERPROOF and ("bị thấm" in lower_t or "vô nước" in lower_t or "ngấm nước" in lower_t):
                pol = Polarity.NEG

            opinions.append(
                {
                    "aspect": aspect.value,
                    "polarity": pol.value,
                    "evidence": matched_kw[0],
                }
            )

    if not opinions:
        opinions.append(
            {
                "aspect": Aspect.GENERAL.value,
                "polarity": default_pol.value,
                "evidence": clean_t[:30],
            }
        )

    is_informative = len(clean_t.split()) >= 2 and stripped_alpha not in ("hàng chất lượng",)
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
