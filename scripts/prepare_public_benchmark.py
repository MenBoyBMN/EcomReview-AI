"""Prepare Track 1 Public Benchmark Dataset from UIT-ViSFD."""

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

CACHE_DIR = Path("data/cache")
PUBLIC_DIR = Path("data/public")
CACHE_CSV = CACHE_DIR / "ViSFD.csv"

# Deterministic mapping from UIT-ViSFD fine-grained smartphone aspects to 5 MacroAspects
ASPECT_TO_MACRO: dict[str, str] = {
    "BATTERY": "PERFORMANCE_FUNCTION",
    "SCREEN": "PERFORMANCE_FUNCTION",
    "PERFORMANCE": "PERFORMANCE_FUNCTION",
    "CAMERA": "PERFORMANCE_FUNCTION",
    "FEATURES": "PERFORMANCE_FUNCTION",
    "STORAGE": "PERFORMANCE_FUNCTION",
    "DESIGN": "QUALITY_DESIGN",
    "PRICE": "PRICE_VALUE",
    "SER&ACC": "SERVICE_LOGISTICS",
    "GENERAL": "GENERAL",
    "OTHERS": "GENERAL",
}

ASPECT_KEYWORDS: dict[str, list[str]] = {
    "BATTERY": ["pin", "bin", "sạc", "dung lượng"],
    "SCREEN": ["màn hình", "màn", "hiển thị", "cảm ứng", "kính"],
    "PERFORMANCE": ["mượt", "lag", "đơ", "chơi game", "cấu hình", "tốc độ", "load", "máy"],
    "CAMERA": ["camera", "chụp", "ảnh", "cam", "hình"],
    "FEATURES": ["vân tay", "loa", "phần mềm", "âm thanh", "wifi", "sóng", "nfc"],
    "STORAGE": ["bộ nhớ", "dung lượng", "ram", "rom", "gb"],
    "DESIGN": ["thiết kế", "đẹp", "màu", "cầm", "kiểu dáng", "nhỏ gọn", "vỏ"],
    "PRICE": ["giá", "tiền", "đắt", "rẻ", "vừa túi", "kinh tế"],
    "SER&ACC": ["nhân viên", "tư vấn", "giao", "phục vụ", "cửa hàng", "tai nghe", "sạc"],
    "GENERAL": ["máy", "sản phẩm", "tổng quan", "dùng", "xài", "ok"],
}


def parse_visfd_label(label_str: str, text: str) -> list[dict[str, str]]:
    """Parse ViSFD label format e.g. '{CAMERA#Positive};{BATTERY#Negative};' into opinions list."""
    if not isinstance(label_str, str):
        return []

    opinions: list[dict[str, str]] = []
    matches = re.findall(r"\{([^}]+)\}", label_str)
    text_lower = text.lower()

    for match in matches:
        if "#" in match:
            raw_aspect, raw_pol = match.split("#", 1)
            raw_aspect = raw_aspect.strip().upper()
            pol_normalized = raw_pol.strip().lower()
        else:
            raw_aspect = match.strip().upper()
            pol_normalized = "neutral"

        if raw_aspect not in ASPECT_TO_MACRO:
            continue

        macro_aspect = ASPECT_TO_MACRO[raw_aspect]

        # Extract evidence snippet
        evidence = raw_aspect
        keywords = ASPECT_KEYWORDS.get(raw_aspect, [])
        for kw in keywords:
            if kw in text_lower:
                idx = text_lower.find(kw)
                start = max(0, idx - 15)
                end = min(len(text), idx + len(kw) + 20)
                snippet = text[start:end].strip()
                if snippet:
                    evidence = snippet
                    break

        opinions.append(
            {
                "aspect": macro_aspect,
                "original_aspect": raw_aspect,
                "polarity": pol_normalized,
                "evidence": evidence,
            }
        )

    return opinions


def derive_overall_sentiment(opinions: list[dict[str, str]], n_star: int | float) -> str:
    """Infer overall sentiment based on opinion counts and user star rating."""
    pos_count = sum(1 for op in opinions if op["polarity"] == "positive")
    neg_count = sum(1 for op in opinions if op["polarity"] == "negative")

    if pos_count > neg_count:
        return "positive"
    if neg_count > pos_count:
        return "negative"
    if pos_count == neg_count and pos_count > 0:
        return "positive" if n_star >= 4 else "negative"

    if n_star >= 4:
        return "positive"
    if n_star <= 2:
        return "negative"
    return "neutral"


def prepare_benchmark():
    """Process ViSFD dataset into standard public benchmark files."""
    if not CACHE_CSV.exists():
        raise FileNotFoundError(f"Cache CSV not found at {CACHE_CSV}")

    df = pd.read_csv(CACHE_CSV)
    df = df.dropna(subset=["comment", "label"])
    df["comment"] = df["comment"].astype(str).str.strip()
    df = df[df["comment"] != ""]

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    # Process each split
    splits_data: dict[str, list[dict[str, Any]]] = {"train": [], "dev": [], "test": []}

    for _, row in df.iterrows():
        split_type = str(row["type"]).strip().lower()
        if split_type not in splits_data:
            continue

        text = row["comment"]
        n_star = row.get("n_star", 5)
        opinions = parse_visfd_label(str(row["label"]), text)
        if not opinions:
            continue

        overall_sent = derive_overall_sentiment(opinions, n_star)
        row_id = f"visfd_{split_type}_{row['index']}"

        clean_opinions = [
            {"aspect": op["aspect"], "polarity": op["polarity"], "evidence": op["evidence"]}
            for op in opinions
        ]

        record = {
            "id": row_id,
            "text": text,
            "source_type": "public_benchmark",
            "opinions": clean_opinions,
            "overall_sentiment": overall_sent,
            "informative": True,
        }
        splits_data[split_type].append(record)

    # Stratified downsampling for Week 2-4 tasks:
    # Train: 1,500 samples
    # Val: 300 samples
    # Test: exactly 400 samples (Roadmap Week 2 specification)
    rng = 42

    df_train = pd.DataFrame(splits_data["train"]).sample(n=1500, random_state=rng)
    df_val = pd.DataFrame(splits_data["dev"]).sample(n=300, random_state=rng)
    df_test = pd.DataFrame(splits_data["test"]).sample(n=400, random_state=rng)

    for name, sample_df in [("train", df_train), ("val", df_val), ("test", df_test)]:
        out_path = PUBLIC_DIR / f"{name}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for item in sample_df.to_dict(orient="records"):
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"[+] Saved {name}: {len(sample_df)} records -> {out_path}")

    # Summary metadata
    meta = {
        "dataset_name": "UIT-ViSFD (Normalized)",
        "source": "Luong Luc Phan et al. (2021) - Knowledge Science, Engineering and Management",
        "macro_aspects": list(set(ASPECT_TO_MACRO.values())),
        "split_counts": {
            "train": len(df_train),
            "val": len(df_val),
            "test": len(df_test),
        },
        "test_sentiment_distribution": df_test["overall_sentiment"].value_counts().to_dict(),
    }
    meta_path = PUBLIC_DIR / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"[+] Metadata written to: {meta_path}")


if __name__ == "__main__":
    prepare_benchmark()

# CreBy: MenBoyBMN
