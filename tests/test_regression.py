"""Regression test suite for Post-Hoc Fixes and Week 9 deliverables (Task 9.2)."""

from __future__ import annotations

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


# CreBy: MenBoyBMN
