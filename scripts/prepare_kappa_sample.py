"""Prepare 50 randomized blind samples for Round 2 human annotation (Cohen's Kappa).

Extracts 50 random samples from gold_round1.jsonl, removes previous labels,
shuffles order, and exports to CSV and Excel for human annotator.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    round1_path = Path("data/gold/gold_round1.jsonl")
    if not round1_path.exists():
        raise FileNotFoundError(f"Missing {round1_path}")

    records = []
    with open(round1_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    # Fix seed for reproducibility
    rng = np.random.default_rng(42)
    indices = rng.choice(len(records), size=50, replace=False)
    selected_samples = [records[i] for i in indices]

    # Save reference for calculation
    ref_path = Path("data/gold/kappa_50_round1_reference.json")
    with open(ref_path, "w", encoding="utf-8") as f:
        json.dump(selected_samples, f, ensure_ascii=False, indent=2)

    # Prepare blind annotation template
    blind_rows = []
    for idx, s in enumerate(selected_samples, start=1):
        blind_rows.append(
            {
                "sample_order": idx,
                "review_id": s["id"],
                "text": s["text"],
                "overall_sentiment": "",  # positive / negative / neutral
                "WATERPROOF": "",  # pos / neg / neu / trống (nếu không có)
                "MATERIAL_DURABILITY": "",  # pos / neg / neu / trống
                "FIT_SIZE": "",  # pos / neg / neu / trống
                "COMFORT_USABILITY": "",  # pos / neg / neu / trống
                "PRICE_VALUE": "",  # pos / neg / neu / trống
                "PACKAGING_SHIPPING": "",  # pos / neg / neu / trống
                "CUSTOMER_SERVICE": "",  # pos / neg / neu / trống
                "ACCESSIBILITY_DESIGN": "",  # pos / neg / neu / trống
                "GENERAL": "",  # pos / neg / neu / trống (nếu khen/chê chung)
                "evidence_notes": "",  # Trích dẫn nguyên văn 1-15 từ
                "informative": "",  # TRUE / FALSE
            }
        )

    df_blind = pd.DataFrame(blind_rows)
    csv_out = Path("data/gold/kappa_50_blind.csv")
    xlsx_out = Path("data/gold/kappa_50_blind.xlsx")

    df_blind.to_csv(csv_out, index=False, encoding="utf-8-sig")
    df_blind.to_excel(xlsx_out, index=False)

    print(f"Exported 50 blind samples to {csv_out} and {xlsx_out}")
    print(f"Saved round 1 reference labels to {ref_path}")


if __name__ == "__main__":
    main()

# CreBy: MenBoyBMN
