"""Generate and validate 80 high-diversity synthetic raincoat review samples for Dev Set.

Distribution follows Roadmap Week 2 Task 2.1:
- 30% (24 samples): Teencode and social abbreviations (ko, sp, dc, sz, mik...)
- 20% (16 samples): No Vietnamese diacritics (ao mua, mac vua, di mua...)
- 20% (16 samples): Emojis with explicit sentiment tokens (😍, 👍, 😡, 👎...)
- 15% (12 samples): Sarcasm & ironic expressions
- 15% (12 samples): Multi-aspect mixed sentiment

IMPORTANT: synthetic_dev samples are EXCLUSIVELY used in dev.jsonl for prompt tuning,
few-shot calibration, and threshold selection. NEVER leak into test_locked.jsonl.
"""

import json
from pathlib import Path

from ecomreview.schemas import ReviewAnalysis

GOLD_DIR = Path("data/gold")
OUTPUT_FILE = GOLD_DIR / "synthetic_dev.jsonl"


def validate_synthetic_dev(file_path: Path = OUTPUT_FILE) -> int:
    """Validate each line in synthetic_dev.jsonl against the ReviewAnalysis Pydantic schema."""
    if not file_path.exists():
        raise FileNotFoundError(f"Synthetic dev file not found: {file_path}")

    valid_count = 0
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            # Schema validation
            analysis = ReviewAnalysis(
                overall_sentiment=data["overall_sentiment"],
                opinions=data["opinions"],
                informative=data.get("informative", True),
            )
            assert analysis.overall_sentiment is not None
            assert isinstance(data.get("noise_type"), str)
            valid_count += 1

    print(f"[+] Verified {valid_count} synthetic dev samples against ReviewAnalysis schema.")
    return valid_count


if __name__ == "__main__":
    validate_synthetic_dev()

# CreBy: MenBoyBMN
