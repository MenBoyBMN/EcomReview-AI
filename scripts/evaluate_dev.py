"""Run comparative evaluation of Baselines (B1, B2) and Proposed A1 on dev.jsonl.

Outputs:
- results/dev_comparison_v1.csv
- results/a1_v1_dev_errors.json (10 qualitative error cases for Week 4 prompt iteration)
"""

import json
import logging
import tempfile
import time
from pathlib import Path

import pandas as pd
from sklearn.model_selection import KFold

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


def run_b2_oof_dev(
    public_train_path: Path, gold_dev: list[dict], seed: int = 42
) -> tuple[list[ReviewAnalysis], float]:
    """Evaluate B2 on dev.jsonl using 5-fold out-of-fold predictions to prevent train=test overfit."""
    kf = KFold(n_splits=5, shuffle=True, random_state=seed)
    oof_preds: list[ReviewAnalysis | None] = [None] * len(gold_dev)
    latencies: list[float] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_fold_path = Path(tmpdir) / "fold_train.jsonl"
        for train_idx, val_idx in kf.split(gold_dev):
            with open(tmp_fold_path, "w", encoding="utf-8") as f:
                for idx in train_idx:
                    f.write(json.dumps(gold_dev[idx], ensure_ascii=False) + "\n")

            fold_b2 = B2TfidfAnalyzer(random_state=seed)
            fold_b2.fit(public_train_path, tmp_fold_path)

            for idx in val_idx:
                start_t = time.perf_counter()
                pred = fold_b2.analyze_review(gold_dev[idx]["text"])
                latencies.append((time.perf_counter() - start_t) * 1000)
                oof_preds[idx] = pred

    avg_lat = sum(latencies) / len(latencies)
    return [p for p in oof_preds if p is not None], avg_lat


def main():
    dev_path = Path("data/gold/dev.jsonl")
    pub_train_path = Path("data/public/train.jsonl")
    pub_val_path = Path("data/public/val.jsonl")
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)

    if not dev_path.exists():
        raise FileNotFoundError(f"Missing {dev_path}")

    gold_dev = load_jsonl(dev_path)
    texts_dev = [item["text"] for item in gold_dev]
    logger.info("Loaded %d dev samples from %s", len(gold_dev), dev_path)

    # 1. Initialize & Fit full B2 model artifact for downstream use
    logger.info("Initializing Analyzers...")
    b1 = B1RuleAnalyzer()

    model_path = Path("models/b2_tfidf_pipeline.joblib")
    logger.info("Training and saving full B2 TF-IDF pipeline to %s...", model_path)
    b2 = B2TfidfAnalyzer(random_state=42)
    b2.fit(pub_train_path, dev_path)
    b2.save(model_path)

    a1 = A1GeminiAnalyzer(
        model_id="gemini-3.5-flash",
        prompt_path="prompts/analyzer_v1.md",
        cache_dir="data/cache",
    )

    systems = [
        ("B1: Rule & Lexicon", b1, 0.0),
        ("B2: TF-IDF + LogReg (5-Fold CV)", b2, 0.0),
        ("A1: Gemini Flash (v1)", a1, 0.05),
    ]

    rows = []
    a1_predictions: list[ReviewAnalysis] = []

    for name, analyzer, cost_1k in systems:
        logger.info("Evaluating %s on dev.jsonl...", name)
        if name.startswith("B2"):
            preds, avg_lat = run_b2_oof_dev(pub_train_path, gold_dev, seed=42)
        elif name.startswith("A1"):
            from concurrent.futures import ThreadPoolExecutor

            def _eval_one(t: str) -> tuple[ReviewAnalysis, float]:
                st = time.perf_counter()
                p = analyzer.analyze_review(t)
                return p, (time.perf_counter() - st) * 1000

            with ThreadPoolExecutor(max_workers=6) as ex:
                out_pairs = list(ex.map(_eval_one, texts_dev))
            preds = [p for p, _ in out_pairs]
            latencies = [lat for _, lat in out_pairs]
            avg_lat = sum(latencies) / len(latencies)
        else:
            preds = []
            latencies = []
            for text in texts_dev:
                start_t = time.perf_counter()
                pred = analyzer.analyze_review(text)
                latencies.append((time.perf_counter() - start_t) * 1000)
                preds.append(pred)
            avg_lat = sum(latencies) / len(latencies)

        if name.startswith("A1"):
            a1_predictions = preds

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

    # 1b. Also evaluate B1 and B2 on 200 samples of data/public/val.jsonl (Task 3.5)
    if pub_val_path.exists():
        pub_val_records = load_jsonl(pub_val_path)[:200]
        pub_val_texts = [item["text"] for item in pub_val_records]
        pub_rows = []
        for name, is_b2 in [("B1: Rule & Lexicon", False), ("B2: TF-IDF + LogReg", True)]:
            p_list: list[ReviewAnalysis] = []
            lats: list[float] = []
            for text in pub_val_texts:
                st = time.perf_counter()
                pred = b2.analyze_review(text, is_macro_track=True) if is_b2 else b1.analyze_review(text)
                lats.append((time.perf_counter() - st) * 1000)
                p_list.append(pred)
            m_pub = evaluate_predictions(pub_val_records, p_list, texts=pub_val_texts, n_boot=1000, seed=42)
            ci_o = m_pub["overall_sentiment_ci"]
            pub_rows.append(
                {
                    "Track": "Public Benchmark (val 200)",
                    "System": name,
                    "Overall_F1": f"{m_pub['overall_sentiment_f1']:.4f} [{ci_o[1]:.4f} - {ci_o[2]:.4f}]",
                    "Latency_ms": f"{sum(lats) / len(lats):.1f}",
                }
            )
        pd.DataFrame(pub_rows).to_csv(results_dir / "public_val_comparison_v1.csv", index=False, encoding="utf-8-sig")
        logger.info("Saved Public Benchmark val comparison to results/public_val_comparison_v1.csv")

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
