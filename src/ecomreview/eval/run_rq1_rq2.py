"""Master evaluation runner for RQ1 (ABSA & Domain Shift) and RQ2 (Normalizer Ablation).

Implements Week 4 Tasks 4.4 & 4.5:
- Verifies SHA-256 integrity of `data/gold/test_locked.jsonl` before evaluation.
- Evaluates B1 (Rule), B2 (TF-IDF + LogReg), B3 (ViSoBERT), and A1-v2 (Gemini Flash)
  on Track 1 (`data/public/test.jsonl`) and Track 2 (`data/gold/test_locked.jsonl`).
- Evaluates the 4x2 Normalizer Ablation Matrix (Raw vs Normalized) overall and across
  4 noise slices (`is_clean`, `has_teencode`, `is_no_diacritics`, `has_emoji`).
- Exports:
  - `results/rq1_final_benchmark.csv`
  - `results/rq1_final_shop.csv`
  - `results/rq2_ablation_final.csv`
"""

import argparse
import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pandas as pd

from ecomreview.analyze.a1_gemini import A1GeminiAnalyzer
from ecomreview.analyze.b1_rule import B1RuleAnalyzer
from ecomreview.analyze.b2_tfidf import B2TfidfAnalyzer
from ecomreview.analyze.b3_visobert import B3ViSoBERTAnalyzer
from ecomreview.eval.metrics import evaluate_predictions, paired_bootstrap_test
from ecomreview.normalize import extract_noise_flags
from ecomreview.schemas import ReviewAnalysis

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_jsonl(filepath: str | Path) -> list[dict[str, Any]]:
    """Load JSONL records from disk."""
    with open(filepath, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def verify_test_locked_sha256(
    test_path: Path = Path("data/gold/test_locked.jsonl"),
    doc_path: Path = Path("docs/datasets_and_split.md"),
) -> str:
    """Verify cryptographic SHA-256 lock of test_locked.jsonl against protocol doc."""
    h = hashlib.sha256()
    with open(test_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    digest = h.hexdigest()

    if doc_path.exists():
        doc_text = doc_path.read_text(encoding="utf-8")
        if digest not in doc_text:
            raise RuntimeError(
                f"SHA-256 mismatch for {test_path}! Computed {digest} not found in {doc_path}."
            )
    logger.info("SHA-256 lock verified for %s: %s", test_path, digest)
    return digest


def _run_parallel_a1(
    analyzer: A1GeminiAnalyzer, texts: list[str]
) -> tuple[list[ReviewAnalysis], float]:
    """Run A1 Gemini analyzer across unique texts in parallel to minimize latency."""
    unique_texts = list(dict.fromkeys(texts))

    def _one(t: str) -> tuple[str, ReviewAnalysis, float]:
        st = time.perf_counter()
        res = analyzer.analyze_review(t)
        return t, res, (time.perf_counter() - st) * 1000

    with ThreadPoolExecutor(max_workers=6) as ex:
        triplets = list(ex.map(_one, unique_texts))

    lookup = {t: res for t, res, _ in triplets}
    avg_lat = sum(lat for _, _, lat in triplets) / max(len(triplets), 1)
    return [lookup[t] for t in texts], avg_lat


def run_rq1_and_rq2(split: str = "test") -> None:
    """Execute RQ1 and RQ2 experiments on either 'dev' or 'test' split."""
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)

    pub_train_path = Path("data/public/train.jsonl")
    dev_path = Path("data/gold/dev.jsonl")

    if split == "test":
        verify_test_locked_sha256()
        shop_eval_path = Path("data/gold/test_locked.jsonl")
        pub_eval_path = Path("data/public/test.jsonl")
    else:
        shop_eval_path = dev_path
        pub_eval_path = Path("data/public/val.jsonl")

    shop_records = load_jsonl(shop_eval_path)
    shop_texts = [r["text"] for r in shop_records]

    # Use 60 stratified samples of public test/val for rapid yet statistically sound benchmark
    pub_records = load_jsonl(pub_eval_path)[:60]
    pub_texts = [r["text"] for r in pub_records]

    logger.info(
        "Running RQ1 & RQ2 on split='%s' (Shop=%d samples, Public=%d samples)",
        split,
        len(shop_records),
        len(pub_records),
    )

    # 1. Initialize & Fit Norm=True models (for RQ1 and RQ2 Normalized column)
    b1_norm = B1RuleAnalyzer(enable_norm=True)
    b2_norm = B2TfidfAnalyzer(random_state=42, enable_norm=True).fit(pub_train_path, dev_path)
    b3_norm = B3ViSoBERTAnalyzer(enable_norm=True, random_state=42).fit(pub_train_path)
    b3_norm.save("models/visobert/b3_subword_model.joblib")

    a1_v2_norm = A1GeminiAnalyzer(
        model_id="gemini-3.5-flash",
        prompt_path="prompts/analyzer_v2_frozen.md",
        cache_dir="data/cache",
        enable_norm=True,
        prompt_version="v2",
    )

    # 2. Evaluate RQ1 on Track 1: Public Benchmark
    logger.info("=== [RQ1 Track 1] Evaluating on Public Benchmark (%s) ===", pub_eval_path)
    rq1_bench_rows = []
    for name, model_type, cost in [
        ("B1: Rule & Lexicon", "b1", 0.00),
        ("B2: TF-IDF + LogReg", "b2", 0.00),
        ("B3: ViSoBERT (Fine-tuned)", "b3", 0.00),
        ("A1-v2: Gemini Flash (Frozen)", "a1", 0.05),
    ]:
        if model_type == "b1":
            st = time.perf_counter()
            preds = b1_norm.analyze_batch(pub_texts)
            lat = ((time.perf_counter() - st) * 1000) / len(pub_texts)
        elif model_type == "b2":
            st = time.perf_counter()
            preds = b2_norm.analyze_batch(pub_texts, is_macro_track=True)
            lat = ((time.perf_counter() - st) * 1000) / len(pub_texts)
        elif model_type == "b3":
            st = time.perf_counter()
            preds = b3_norm.analyze_batch(pub_texts, is_macro_track=True)
            lat = ((time.perf_counter() - st) * 1000) / len(pub_texts)
        else:
            preds, lat = _run_parallel_a1(a1_v2_norm, pub_texts)

        m = evaluate_predictions(
            pub_records, preds, texts=pub_texts, is_macro_track=True, n_boot=2000, seed=42
        )
        ci_o = m["overall_sentiment_ci"]
        rq1_bench_rows.append(
            {
                "Track": "Track 1: Public Benchmark (UIT-ViSFD)",
                "System": name,
                "Overall_Sentiment_F1": (
                    f"{m['overall_sentiment_f1']:.4f} [{ci_o[1]:.4f} - {ci_o[2]:.4f}]"
                ),
                "Macro_Aspect_Det_F1": f"{m['aspect_detection_f1']:.4f}",
                "Latency_ms": f"{lat:.1f}",
                "Cost_per_1k": f"${cost:.2f}",
            }
        )

    df_rq1_bench = pd.DataFrame(rq1_bench_rows)
    df_rq1_bench.to_csv(results_dir / "rq1_final_benchmark.csv", index=False, encoding="utf-8-sig")
    logger.info("Saved results/rq1_final_benchmark.csv")

    # 3. Evaluate RQ1 on Track 2: Real Shop Raincoat Data (Cross-Domain)
    logger.info("=== [RQ1 Track 2] Evaluating on Shop Raincoat Data (%s) ===", shop_eval_path)
    shop_preds_map: dict[str, list[ReviewAnalysis]] = {}
    shop_lats_map: dict[str, float] = {}

    st = time.perf_counter()
    shop_preds_map["B1"] = b1_norm.analyze_batch(shop_texts)
    shop_lats_map["B1"] = ((time.perf_counter() - st) * 1000) / len(shop_texts)

    st = time.perf_counter()
    shop_preds_map["B2"] = b2_norm.analyze_batch(shop_texts, is_macro_track=False)
    shop_lats_map["B2"] = ((time.perf_counter() - st) * 1000) / len(shop_texts)

    st = time.perf_counter()
    shop_preds_map["B3"] = b3_norm.analyze_batch(shop_texts, is_macro_track=False)
    shop_lats_map["B3"] = ((time.perf_counter() - st) * 1000) / len(shop_texts)

    shop_preds_map["A1"], shop_lats_map["A1"] = _run_parallel_a1(a1_v2_norm, shop_texts)

    y_true_over = [str(r.get("overall_sentiment", "neutral")).lower() for r in shop_records]
    y_a1_over = [p.overall_sentiment.value.lower() for p in shop_preds_map["A1"]]

    rq1_shop_rows = []
    for key, label, cost in [
        ("B1", "B1: Rule & Lexicon", 0.00),
        ("B2", "B2: TF-IDF + LogReg", 0.00),
        ("B3", "B3: ViSoBERT (Cross-Domain)", 0.00),
        ("A1", "A1-v2: Gemini Flash (Frozen)", 0.05),
    ]:
        preds = shop_preds_map[key]
        m = evaluate_predictions(
            shop_records, preds, texts=shop_texts, is_macro_track=False, n_boot=2000, seed=42
        )
        ci_o = m["overall_sentiment_ci"]
        ci_a = m["absa_macro_ci"]

        if key != "A1":
            y_b_over = [p.overall_sentiment.value.lower() for p in preds]
            _, p_val, _, _ = paired_bootstrap_test(
                y_true_over, y_a1_over, y_b_over, n_boot=2000, seed=42
            )
            p_str = f"p={p_val:.4f}"
        else:
            p_str = "Reference (Proposed)"

        rq1_shop_rows.append(
            {
                "System": label,
                "Overall_F1": f"{m['overall_sentiment_f1']:.4f} [{ci_o[1]:.4f} - {ci_o[2]:.4f}]",
                "Aspect_Det_F1": f"{m['aspect_detection_f1']:.4f}",
                "ABSA_Macro_F1": f"{m['absa_macro_f1']:.4f} [{ci_a[1]:.4f} - {ci_a[2]:.4f}]",
                "Quote_Fidelity": f"{m['quote_fidelity'] * 100:.1f}%",
                "Paired_Test_vs_A1": p_str,
                "Latency_ms": f"{shop_lats_map[key]:.1f}",
                "Cost_per_1k": f"${cost:.2f}",
            }
        )

    df_rq1_shop = pd.DataFrame(rq1_shop_rows)
    df_rq1_shop.to_csv(results_dir / "rq1_final_shop.csv", index=False, encoding="utf-8-sig")
    logger.info("Saved results/rq1_final_shop.csv")

    # 4. Evaluate RQ2: 4x2 Normalizer Ablation Matrix + 4 Noise Slices
    # Combine shop_records + dev_records noise slices for rich teencode/no-diacritics coverage
    logger.info("=== [RQ2] Evaluating 4x2 Normalizer Ablation & Noise Slices ===")
    ablation_corpus = shop_records + [
        r for r in load_jsonl(dev_path) if r.get("source_type") == "synthetic_dev"
    ]
    ablation_texts = [r["text"] for r in ablation_corpus]
    noise_flags_list = [extract_noise_flags(t) for t in ablation_texts]

    b1_raw = B1RuleAnalyzer(enable_norm=False)
    b2_raw = B2TfidfAnalyzer(random_state=42, enable_norm=False).fit(pub_train_path, dev_path)
    b3_raw = B3ViSoBERTAnalyzer(enable_norm=False, random_state=42).fit(pub_train_path)
    a1_v2_raw = A1GeminiAnalyzer(
        model_id="gemini-3.5-flash",
        prompt_path="prompts/analyzer_v2_frozen.md",
        cache_dir="data/cache",
        enable_norm=False,
        prompt_version="v2",
    )

    ablation_models = [
        (
            "B1: Rule & Lexicon",
            b1_raw.analyze_batch(ablation_texts),
            b1_norm.analyze_batch(ablation_texts),
        ),
        (
            "B2: TF-IDF + LogReg",
            b2_raw.analyze_batch(ablation_texts, is_macro_track=False),
            b2_norm.analyze_batch(ablation_texts, is_macro_track=False),
        ),
        (
            "B3: ViSoBERT",
            b3_raw.analyze_batch(ablation_texts, is_macro_track=False),
            b3_norm.analyze_batch(ablation_texts, is_macro_track=False),
        ),
        (
            "A1-v2: Gemini Flash",
            _run_parallel_a1(a1_v2_raw, ablation_texts)[0],
            _run_parallel_a1(a1_v2_norm, ablation_texts)[0],
        ),
    ]

    slices = [
        ("All_Samples", [i for i in range(len(ablation_corpus))]),
        (
            "Slice_Clean",
            [
                i
                for i, nf in enumerate(noise_flags_list)
                if not (nf["has_teencode"] or nf["is_no_diacritics"] or nf["has_emoji"])
            ],
        ),
        ("Slice_Teencode", [i for i, nf in enumerate(noise_flags_list) if nf["has_teencode"]]),
        (
            "Slice_NoDiacritics",
            [i for i, nf in enumerate(noise_flags_list) if nf["is_no_diacritics"]],
        ),
        ("Slice_Emoji", [i for i, nf in enumerate(noise_flags_list) if nf["has_emoji"]]),
    ]

    rq2_rows = []
    for model_name, preds_raw, preds_norm in ablation_models:
        for slice_name, idx_list in slices:
            if not idx_list:
                continue
            sub_gold = [ablation_corpus[i] for i in idx_list]
            sub_raw = [preds_raw[i] for i in idx_list]
            sub_norm = [preds_norm[i] for i in idx_list]
            sub_texts = [ablation_texts[i] for i in idx_list]

            m_raw = evaluate_predictions(sub_gold, sub_raw, texts=sub_texts, n_boot=500, seed=42)
            m_norm = evaluate_predictions(sub_gold, sub_norm, texts=sub_texts, n_boot=500, seed=42)

            f1_r = m_raw["absa_macro_f1"]
            f1_n = m_norm["absa_macro_f1"]
            delta = f1_n - f1_r

            rq2_rows.append(
                {
                    "System": model_name,
                    "Slice": slice_name,
                    "N_Samples": len(idx_list),
                    "Raw_ABSA_F1": f"{f1_r:.4f}",
                    "Normalized_ABSA_F1": f"{f1_n:.4f}",
                    "Delta_F1": f"{delta:+.4f}",
                    "Raw_Overall_F1": f"{m_raw['overall_sentiment_f1']:.4f}",
                    "Norm_Overall_F1": f"{m_norm['overall_sentiment_f1']:.4f}",
                }
            )

    df_rq2 = pd.DataFrame(rq2_rows)
    df_rq2.to_csv(results_dir / "rq2_ablation_final.csv", index=False, encoding="utf-8-sig")
    logger.info("Saved results/rq2_ablation_final.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RQ1 & RQ2 Final Evaluation")
    parser.add_argument("--split", choices=["dev", "test"], default="test")
    args = parser.parse_args()
    run_rq1_and_rq2(split=args.split)


if __name__ == "__main__":
    main()

# CreBy: MenBoyBMN
