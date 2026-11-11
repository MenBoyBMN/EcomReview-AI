"""Unit and integration tests for RQ3 Groundedness, Rubric & Adoption Evaluation (Week 8)."""

from __future__ import annotations

import csv
from pathlib import Path

from ecomreview.eval.groundedness import GroundednessEvaluator, bootstrap_mean_ci


def test_bootstrap_mean_ci_deterministic() -> None:
    """Verify bootstrap_mean_ci returns deterministic mean and valid 95% bounds."""
    vals = [80.0, 90.0, 100.0, 100.0, 100.0, 95.0, 85.0, 100.0]
    mean_v, ci_l, ci_h = bootstrap_mean_ci(vals, n_boot=500, seed=42)
    assert 85.0 <= ci_l <= mean_v <= ci_h <= 100.0
    assert bootstrap_mean_ci([], n_boot=100, seed=42) == (0.0, 0.0, 0.0)


def test_groundedness_evaluator_p0_vs_p1() -> None:
    """Verify P1-Full achieves 100% across all 5 groundedness/safety metrics vs P0."""
    evaluator = GroundednessEvaluator()
    res = evaluator.run_rq3_automated_benchmark()
    by_sys = {r["system"]: r for r in res["summary"]}

    p0 = by_sys["P0_Single_Prompt"]
    p1_nc = by_sys["P1_No_Critic"]
    p1_full = by_sys["P1_Full_Proposed"]

    assert p0["evidence_validity_pct"] == 0.0
    assert p0["numeric_consistency_pct"] == 0.0
    assert p0["critic_passed"] == 0.0

    assert p1_nc["evidence_validity_pct"] == 100.0
    assert 0.0 < p1_nc["numeric_consistency_pct"] < 100.0

    assert p1_full["evidence_validity_pct"] == 100.0
    assert p1_full["numeric_consistency_pct"] == 100.0
    assert p1_full["quote_fidelity_pct"] == 100.0
    assert p1_full["structural_completeness_pct"] == 100.0
    assert p1_full["policy_claim_safety_pct"] == 100.0
    assert p1_full["critic_passed"] == 100.0
    assert p1_full["critic_score"] == 5.0


def test_rq3_blind_eval_and_adoption_outputs_exist() -> None:
    """Ensure all Week 8 RQ3 output artifacts are generated and non-empty."""
    required_files = [
        Path("results/rq3_automated.csv"),
        Path("results/blind_ab_pack.md"),
        Path("results/secret_key.json"),
        Path("results/rq3_simulation_ratings.csv"),
        Path("results/rq3_adoption.csv"),
        Path("results/rq3_final_summary.csv"),
        Path("docs/rubric_rq3.md"),
        Path("docs/case_study_shop_aomua.md"),
        Path("docs/report/ch4_rq3_eval.md"),
    ]
    for fp in required_files:
        assert fp.exists(), f"Missing Week 8 deliverable: {fp}"
        assert fp.stat().st_size > 100

    with Path("results/rq3_adoption.csv").open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 25
    decisions = {r["decision"] for r in rows}
    assert decisions.issubset({"APPROVED", "EDITED", "REJECTED"})


# CreBy: MenBoyBMN
