"""Regression test suite for Post-Hoc Fixes and Week 9 deliverables (Task 9.2)."""

from __future__ import annotations

import csv
from pathlib import Path

from ecomreview.analyze.b1_rule import B1RuleAnalyzer
from ecomreview.normalize import normalize_social_text
from ecomreview.schemas import Aspect


def test_fix_01_compound_word_over_normalization_guard() -> None:
    """Ensure 'chất liệu', 'chất vải', 'chat với shop' are not distorted by TEENCODE_MAP."""
    raw = "Chất liệu vải dù rất dày, chất vải mịn nhưng chat với shop hơi chậm."
    norm = normalize_social_text(raw, enable=True)

    assert "chất liệu" in norm
    assert "chất vải" in norm
    assert "chat với shop" in norm
    assert "chất lượng liệu" not in norm
    assert "chất lượng vải" not in norm

    # Standalone slang 'chất' must still expand to 'chất lượng'
    slang = "Áo mưa này cực chất luôn!"
    assert "chất lượng" in normalize_social_text(slang, enable=True)


def test_fix_01_b1_detects_material_durability_with_norm_on() -> None:
    """Verify B1RuleAnalyzer detects MATERIAL_DURABILITY when 'chất liệu' is normalized."""
    b1 = B1RuleAnalyzer(enable_norm=True)
    res = b1.analyze_review("Chất liệu áo mưa dày dặn chắc chắn lắm")
    aspects = {op.aspect for op in res.opinions}
    assert Aspect.MATERIAL_DURABILITY in aspects


def test_week9_error_taxonomy_figures_and_video_exist() -> None:
    """Verify all Week 9 error analysis, figures, architecture docs, and demo video exist."""
    expected_paths = [
        Path("results/error_taxonomy.csv"),
        Path("results/post_hoc_fixes.csv"),
        Path("docs/error_analysis.md"),
        Path("docs/architecture.md"),
        Path("docs/api_reference.md"),
        Path("docs/demo_script.md"),
        Path("docs/report/ch4_error_analysis.md"),
        Path("docs/report/ch5_conclusion.md"),
        Path("docs/report/figures/error_pareto.png"),
        Path("docs/report/figures/rq1_comparison.png"),
        Path("docs/report/figures/rq2_ablation.png"),
        Path("docs/report/figures/rq3_critic_ablation.png"),
        Path("demo/EcomReview_AI_Demo.mp4"),
        Path("Makefile"),
    ]
    for p in expected_paths:
        assert p.exists(), f"Missing Week 9 deliverable: {p}"
        assert p.stat().st_size > 100

    with Path("results/error_taxonomy.csv").open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 10
    assert abs(float(rows[-1]["cumulative_pct"]) - 100.0) < 0.1


def test_week10_submission_package_and_defense_qa_exist() -> None:
    """Verify all Week 10 submission package files and 30 Q&A bank exist and pass audit."""
    expected_w10 = [
        Path("submission/01_BaoCao_EcomReview_AI.md"),
        Path("submission/01_BaoCao_EcomReview_AI.html"),
        Path("submission/01_BaoCao_EcomReview_AI.docx"),
        Path("submission/02_Slide_BaoVe_EcomReview_AI.md"),
        Path("submission/02_Slide_BaoVe_EcomReview_AI.pptx"),
        Path("submission/03_Checklist_12_YeuCau.md"),
        Path("docs/defense_qa_bank.md"),
        Path("docs/mock_defense_notes.md"),
    ]
    for p in expected_w10:
        assert p.exists(), f"Missing Week 10 deliverable: {p}"
        assert p.stat().st_size > 500

    qa_text = Path("docs/defense_qa_bank.md").read_text(encoding="utf-8")
    assert "Câu 30:" in qa_text


# CreBy: MenBoyBMN
