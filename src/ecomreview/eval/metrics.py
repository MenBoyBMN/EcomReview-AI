"""Statistical evaluation framework and metrics for ABSA and sentiment analysis.

Includes Macro-F1, End-to-End ABSA F1, Evidence Fidelity, and Bootstrap 95% CI.
"""

from typing import Any, Sequence

import numpy as np
from sklearn.metrics import f1_score

from ecomreview.normalize import normalize_social_text
from ecomreview.schemas import Aspect, MacroAspect, ReviewAnalysis


def _fast_cluster_bootstrap_macro_f1(
    sample_true_list: Sequence[Sequence[Any]],
    sample_pred_list: Sequence[Sequence[Any]],
    n_boot: int = 2000,
    seed: int = 42,
) -> tuple[float, float]:
    """Vectorized cluster-bootstrap 95% CI for Macro-F1 using exact confusion counts."""
    n = len(sample_true_list)
    all_labels = sorted(
        {lbl for seq in sample_true_list for lbl in seq}
        | {lbl for seq in sample_pred_list for lbl in seq}
    )
    c_len = len(all_labels)
    if n == 0 or c_len == 0:
        return 0.0, 0.0

    lbl_to_idx = {lbl: i for i, lbl in enumerate(all_labels)}
    tp_mat = np.zeros((n, c_len), dtype=np.float64)
    fp_mat = np.zeros((n, c_len), dtype=np.float64)
    fn_mat = np.zeros((n, c_len), dtype=np.float64)

    for i in range(n):
        for gt, pr in zip(sample_true_list[i], sample_pred_list[i]):
            gi = lbl_to_idx[gt]
            pi = lbl_to_idx[pr]
            if gi == pi:
                tp_mat[i, gi] += 1.0
            else:
                fn_mat[i, gi] += 1.0
                fp_mat[i, pi] += 1.0

    rng = np.random.default_rng(seed)
    weights = np.zeros((n_boot, n), dtype=np.float64)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        weights[b] = np.bincount(idx, minlength=n)

    tp_b = weights @ tp_mat
    fp_b = weights @ fp_mat
    fn_b = weights @ fn_mat

    denom = 2.0 * tp_b + fp_b + fn_b
    f1_per_class = np.divide(2.0 * tp_b, denom, out=np.zeros_like(denom), where=denom > 0)
    active_classes = (tp_b + fp_b + fn_b) > 0
    active_counts = np.maximum(active_classes.sum(axis=1), 1)
    boot_scores = (f1_per_class * active_classes).sum(axis=1) / active_counts

    low, high = np.percentile(boot_scores, [2.5, 97.5])
    return float(low), float(high)


def bootstrap_f1_ci(
    y_true: Sequence[Any],
    y_pred: Sequence[Any],
    n_boot: int = 2000,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Compute point estimate and 95% Bootstrap Confidence Interval for Macro-F1.

    Args:
        y_true: Ground truth labels.
        y_pred: Model predicted labels.
        n_boot: Number of bootstrap iterations (default: 2000).
        seed: Random seed for reproducibility (default: 42).

    Returns:
        tuple of (point_estimate, ci_low_2.5, ci_high_97.5).
    """
    y_t = np.asarray(y_true)
    y_p = np.asarray(y_pred)
    n = len(y_t)

    if n == 0:
        return 0.0, 0.0, 0.0

    point = float(f1_score(y_t, y_p, average="macro", zero_division=0))
    if n == 1:
        return point, point, point

    low, high = _fast_cluster_bootstrap_macro_f1(
        [[x] for x in y_t], [[x] for x in y_p], n_boot=n_boot, seed=seed
    )
    return point, float(low), float(high)


def paired_bootstrap_test(
    y_true: Sequence[Any],
    y_pred_a: Sequence[Any],
    y_pred_b: Sequence[Any],
    n_boot: int = 2000,
    seed: int = 42,
) -> tuple[float, float, float, float]:
    """Perform paired bootstrap hypothesis test comparing Model A and Model B.

    Tests the null hypothesis H0: Macro-F1(A) <= Macro-F1(B).

    Args:
        y_true: Ground truth labels.
        y_pred_a: Predictions from Model A.
        y_pred_b: Predictions from Model B.
        n_boot: Number of bootstrap iterations.
        seed: Random seed for reproducibility.

    Returns:
        tuple of (delta_point, p_value, ci_low, ci_high).
    """
    rng = np.random.default_rng(seed)
    y_t = np.asarray(y_true)
    ya = np.asarray(y_pred_a)
    yb = np.asarray(y_pred_b)
    n = len(y_t)

    if n == 0:
        return 0.0, 1.0, 0.0, 0.0

    score_a = float(f1_score(y_t, ya, average="macro", zero_division=0))
    score_b = float(f1_score(y_t, yb, average="macro", zero_division=0))
    delta_point = score_a - score_b

    deltas = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        sc_a = f1_score(y_t[idx], ya[idx], average="macro", zero_division=0)
        sc_b = f1_score(y_t[idx], yb[idx], average="macro", zero_division=0)
        deltas.append(sc_a - sc_b)

    deltas_arr = np.array(deltas)
    if delta_point > 0:
        p_val = float(np.mean(deltas_arr <= 0))
    elif delta_point < 0:
        p_val = float(np.mean(deltas_arr >= 0))
    else:
        p_val = 1.0

    ci_low, ci_high = np.percentile(deltas_arr, [2.5, 97.5])
    return delta_point, p_val, float(ci_low), float(ci_high)


def _extract_dict_analysis(item: Any) -> tuple[str, dict[str, str], list[str]]:
    """Helper to extract (overall_sentiment, aspect_to_polarity_map, evidence_list)."""
    if isinstance(item, ReviewAnalysis):
        overall = (
            item.overall_sentiment.value
            if hasattr(item.overall_sentiment, "value")
            else str(item.overall_sentiment)
        )
        aspect_map: dict[str, str] = {}
        evidences: list[str] = []
        for op in item.opinions:
            asp_str = op.aspect.value if hasattr(op.aspect, "value") else str(op.aspect)
            pol_str = op.polarity.value if hasattr(op.polarity, "value") else str(op.polarity)
            aspect_map[asp_str] = pol_str
            if op.evidence:
                evidences.append(op.evidence)
        return overall.lower(), aspect_map, evidences

    if isinstance(item, dict):
        overall = str(item.get("overall_sentiment", "neutral")).lower()
        opinions = item.get("opinions", [])
        aspect_map = {}
        evidences = []
        for op in opinions:
            if isinstance(op, dict):
                asp = str(op.get("aspect", "")).strip().upper()
                pol = str(op.get("polarity", "neutral")).strip().lower()
                ev = str(op.get("evidence", "")).strip()
            else:
                asp = str(getattr(op, "aspect", "")).strip().upper()
                pol = str(getattr(op, "polarity", "neutral")).strip().lower()
                ev = str(getattr(op, "evidence", "")).strip()
            if asp:
                aspect_map[asp] = pol
            if ev:
                evidences.append(ev)
        return overall, aspect_map, evidences

    return "neutral", {}, []


def evaluate_predictions(
    gold_list: Sequence[dict[str, Any] | ReviewAnalysis],
    pred_list: Sequence[dict[str, Any] | ReviewAnalysis],
    texts: Sequence[str] | None = None,
    is_macro_track: bool = False,
    n_boot: int = 2000,
    seed: int = 42,
) -> dict[str, Any]:
    """Compute comprehensive ABSA metrics on a dataset.

    Evaluates:
      1. Overall Sentiment Macro-F1 (with Bootstrap 95% CI).
      2. Aspect Detection Macro-F1 (binary present/none per aspect).
      3. End-to-End ABSA Macro-F1 (4 classes: none, positive, negative, neutral
         on Review x Aspect matrix, with Bootstrap 95% CI).
      4. Evidence Quote Fidelity (% verbatim substring matches).

    Args:
        gold_list: Ground truth annotations.
        pred_list: Predicted annotations.
        texts: Optional original review texts for Quote Fidelity evaluation.
        is_macro_track: True for Public benchmark, False for Raincoat domain.
        n_boot: Number of bootstrap iterations for CI.
        seed: Random seed for bootstrap.

    Returns:
        dict containing all metric scores and confidence intervals.
    """
    if len(gold_list) != len(pred_list):
        raise ValueError(
            f"Length mismatch: gold has {len(gold_list)} items, pred has {len(pred_list)} items"
        )

    n_samples = len(gold_list)
    if n_samples == 0:
        return {
            "n_samples": 0,
            "overall_sentiment_f1": 0.0,
            "overall_sentiment_ci": (0.0, 0.0, 0.0),
            "aspect_detection_f1": 0.0,
            "absa_macro_f1": 0.0,
            "absa_macro_ci": (0.0, 0.0, 0.0),
            "quote_fidelity": 0.0,
        }

    # Define target aspect universe
    if is_macro_track:
        target_aspects = [m.value for m in MacroAspect]
    else:
        target_aspects = [a.value for a in Aspect if a != Aspect.GENERAL]

    y_true_overall: list[str] = []
    y_pred_overall: list[str] = []

    # Review-level structures for end-to-end ABSA
    gold_aspect_maps: list[dict[str, str]] = []
    pred_aspect_maps: list[dict[str, str]] = []

    # Evidence checking
    all_pred_evidences: list[tuple[str, str]] = []  # (evidence, text)

    for i in range(n_samples):
        g_over, g_map, _ = _extract_dict_analysis(gold_list[i])
        p_over, p_map, p_evs = _extract_dict_analysis(pred_list[i])

        y_true_overall.append(g_over)
        y_pred_overall.append(p_over)

        gold_aspect_maps.append(g_map)
        pred_aspect_maps.append(p_map)

        if texts is not None and i < len(texts):
            raw_text = str(texts[i])
            for ev in p_evs:
                all_pred_evidences.append((ev, raw_text))

    # 1. Overall Sentiment Macro-F1 + Bootstrap CI
    overall_pt, overall_low, overall_high = bootstrap_f1_ci(
        y_true_overall, y_pred_overall, n_boot=n_boot, seed=seed
    )

    # 2. Aspect Detection Macro-F1 (Binary: present vs absent)
    aspect_det_true: list[int] = []
    aspect_det_pred: list[int] = []

    # 3. End-to-End ABSA (4 classes: none, positive, negative, neutral)
    absa_e2e_true: list[str] = []
    absa_e2e_pred: list[str] = []

    # For review-level cluster bootstrap of ABSA F1
    review_absa_true: list[list[str]] = []
    review_absa_pred: list[list[str]] = []

    for i in range(n_samples):
        g_map = gold_aspect_maps[i]
        p_map = pred_aspect_maps[i]

        cur_true: list[str] = []
        cur_pred: list[str] = []

        for asp in target_aspects:
            # Binary detection
            has_gold = 1 if asp in g_map else 0
            has_pred = 1 if asp in p_map else 0
            aspect_det_true.append(has_gold)
            aspect_det_pred.append(has_pred)

            # End-to-end 4 classes
            pol_gold = g_map.get(asp, "none")
            pol_pred = p_map.get(asp, "none")
            absa_e2e_true.append(pol_gold)
            absa_e2e_pred.append(pol_pred)

            cur_true.append(pol_gold)
            cur_pred.append(pol_pred)

        review_absa_true.append(cur_true)
        review_absa_pred.append(cur_pred)

    aspect_det_f1 = float(
        f1_score(aspect_det_true, aspect_det_pred, average="macro", zero_division=0)
    )
    absa_e2e_pt = float(f1_score(absa_e2e_true, absa_e2e_pred, average="macro", zero_division=0))

    # Review-level cluster bootstrap for ABSA F1 to respect intra-review dependencies
    absa_low, absa_high = _fast_cluster_bootstrap_macro_f1(
        review_absa_true, review_absa_pred, n_boot=n_boot, seed=seed
    )

    # 4. Evidence Quote Fidelity (%)
    if all_pred_evidences:
        valid_evidences = 0
        for ev, raw_txt in all_pred_evidences:
            norm_txt = normalize_social_text(raw_txt, enable=True)
            ev_clean = ev.strip().lower()
            if not ev_clean:
                continue
            if ev_clean in raw_txt.lower() or ev_clean in norm_txt.lower():
                valid_evidences += 1
        quote_fidelity = float(valid_evidences / len(all_pred_evidences))
    else:
        quote_fidelity = 1.0  # Vacuously true if no aspect evidence predicted

    return {
        "n_samples": n_samples,
        "overall_sentiment_f1": round(overall_pt, 4),
        "overall_sentiment_ci": (
            round(overall_pt, 4),
            round(float(overall_low), 4),
            round(float(overall_high), 4),
        ),
        "aspect_detection_f1": round(aspect_det_f1, 4),
        "absa_macro_f1": round(absa_e2e_pt, 4),
        "absa_macro_ci": (
            round(absa_e2e_pt, 4),
            round(float(absa_low), 4),
            round(float(absa_high), 4),
        ),
        "quote_fidelity": round(quote_fidelity, 4),
    }


# CreBy: MenBoyBMN
