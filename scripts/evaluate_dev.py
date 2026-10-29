"""Run comparative evaluation of Baselines (B1, B2) and Proposed A1 on dev.jsonl.

Outputs:
- results/dev_comparison_v1.csv
- results/a1_v1_dev_errors.json (10 qualitative error cases for Week 4 prompt iteration)
"""

import json
import logging
import time
from pathlib import Path

import pandas as pd

from ecomreview.analyze.a1_gemini import A1GeminiAnalyzer
from ecomreview.analyze.b1_rule import B1RuleAnalyzer
from ecomreview.analyze.b2_tfidf import B2TfidfAnalyzer
from ecomreview.eval.metrics import evaluate_predictions
from ecomreview.schemas import ReviewAnalysis

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_jsonl(filepath: str | Path) -> list[dict]:
    """Load JSONL dataset with NaN/Infinity tolerance."""
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def main():
    dev_path = Path("data/gold/dev.jsonl")
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)

    if not dev_path.exists():
        raise FileNotFoundError(f"Missing {dev_path}")

    gold_dev = load_jsonl(dev_path)
    texts_dev = [item["text"] for item in gold_dev]
    logger.info("Loaded %d dev samples from %s", len(gold_dev), dev_path)

    # 1. Initialize systems
    logger.info("Initializing Analyzers...")
    b1 = B1RuleAnalyzer()

    model_path = Path("models/b2_tfidf_pipeline.joblib")
    if not model_path.exists():
        logger.info("Training B2 TF-IDF pipeline...")
        b2 = B2TfidfAnalyzer(random_state=42)
        b2.fit("data/public/train.jsonl", "data/gold/dev.jsonl")
        b2.save(model_path)
    else:
        logger.info("Loading existing B2 TF-IDF pipeline...")
        b2 = B2TfidfAnalyzer.load(model_path)

    a1 = A1GeminiAnalyzer(
        model_id="gemini-3.5-flash",
        prompt_path="prompts/analyzer_v1.md",
        cache_dir="data/cache",
    )

    systems = [
        ("B1: Rule & Lexicon", b1, 0.0),
        ("B2: TF-IDF + LogReg", b2, 0.0),
        ("A1: Gemini Flash (v1)", a1, 0.05),
    ]

    rows = []
    a1_predictions: list[ReviewAnalysis] = []

    for name, analyzer, cost_1k in systems:
        logger.info("Evaluating %s on dev.jsonl...", name)
        preds: list[ReviewAnalysis] = []
        latencies = []

        for text in texts_dev:
            start_t = time.perf_counter()
            pred = analyzer.analyze_review(text)
            latencies.append((time.perf_counter() - start_t) * 1000)
            preds.append(pred)

        if name.startswith("A1"):
            a1_predictions = preds

        avg_lat = sum(latencies) / len(latencies)
        m = evaluate_predictions(gold_dev, preds, texts=texts_dev, n_boot=2000, seed=42)

        ci_over = m["overall_sentiment_ci"]
        ci_absa = m["absa_macro_ci"]

        row = {
            "System": name,
            "Overall_F1": f"{m['overall_sentiment_f1']:.4f} [{ci_over[1]:.4f} - {ci_over[2]:.4f}]",
            "Aspect_F1": f"{m['aspect_detection_f1']:.4f}",
            "ABSA_Macro_F1": f"{m['absa_macro_f1']:.4f} [{ci_absa[1]:.4f} - {ci_absa[2]:.4f}]",
            "Quote_Fidelity": f"{m['quote_fidelity'] * 100:.1f}%",
            "Latency_ms": f"{avg_lat:.1f}",
            "Cost_per_1k": f"${cost_1k:.2f}",
        }
        rows.append(row)
        logger.info("%s -> ABSA Macro-F1: %s, Latency: %.1fms", name, row["ABSA_Macro_F1"], avg_lat)

    # 2. Save CSV comparison
    df_results = pd.DataFrame(rows)
    csv_out = results_dir / "dev_comparison_v1.csv"
    df_results.to_csv(csv_out, index=False, encoding="utf-8-sig")
    logger.info("Saved comparison table to %s", csv_out)

    # 3. Extract 10 Error Cases for A1-v1
    logger.info("Extracting error cases for A1-v1...")
    errors = []
    for i, (gold, pred) in enumerate(zip(gold_dev, a1_predictions)):
        g_overall = str(gold.get("overall_sentiment", "neutral")).lower()
        p_overall = pred.overall_sentiment.value.lower()

        g_opinions = gold.get("opinions", [])
        g_asp_map = {
            (op["aspect"].value if hasattr(op["aspect"], "value") else str(op["aspect"])).upper(): (
                op["polarity"].value if hasattr(op["polarity"], "value") else str(op["polarity"])
            ).lower()
            for op in g_opinions
        }

        p_asp_map = {op.aspect.value.upper(): op.polarity.value.lower() for op in pred.opinions}

        is_error = False
        reasons = []

        if g_overall != p_overall:
            is_error = True
            reasons.append(f"Overall sentiment mismatch: gold={g_overall} vs pred={p_overall}")

        for asp, pol in g_asp_map.items():
            if asp not in p_asp_map:
                is_error = True
                reasons.append(f"Missing aspect: {asp} (gold={pol})")
            elif p_asp_map[asp] != pol:
                is_error = True
                reasons.append(f"Polarity mismatch on {asp}: gold={pol} vs pred={p_asp_map[asp]}")

        for asp, pol in p_asp_map.items():
            if asp not in g_asp_map and asp != "GENERAL":
                is_error = True
                reasons.append(f"Spurious aspect detected: {asp} (pred={pol})")

        if is_error:
            errors.append(
                {
                    "sample_id": gold.get("id", f"sample_{i}"),
                    "text": gold["text"],
                    "gold_overall": g_overall,
                    "pred_overall": p_overall,
                    "gold_opinions": g_opinions,
                    "pred_opinions": [op.model_dump(mode="json") for op in pred.opinions],
                    "reasons": reasons,
                }
            )

    top_errors = errors[:10]
    errors_out = results_dir / "a1_v1_dev_errors.json"
    with open(errors_out, "w", encoding="utf-8") as f:
        json.dump(top_errors, f, ensure_ascii=False, indent=2)
    logger.info("Saved %d qualitative error cases to %s", len(top_errors), errors_out)

    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("\n" + "=" * 80)
    print("BANG KET QUA SO SANH TREN TAP DEV (dev_comparison_v1.csv)")
    print("=" * 80)
    print(df_results.to_markdown(index=False))
    print("=" * 80)


if __name__ == "__main__":
    main()

# CreBy: MenBoyBMN
