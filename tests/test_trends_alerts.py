"""Tests for chronological trends, two-proportion z-tests, and early warning alerts."""

from ecomreview.agent.tools_aggregator import (
    detect_trend_alerts,
    get_aspect_trend,
    get_platform_comparison,
    two_proportion_ztest,
)
from ecomreview.db.database import DatabaseManager


class TestTrendsAndAlerts:
    """Validate zero-hallucination statistical functions."""

    def test_two_proportion_ztest_math(self):
        """Verify two-proportion z-statistic against known values."""
        # 10/100 (10%) vs 30/100 (30%)
        z, p = two_proportion_ztest(10, 100, 30, 100)
        assert z > 0
        assert p < 0.01

        # Identical proportions should yield z=0 and p=1
        z_id, p_id = two_proportion_ztest(15, 50, 15, 50)
        assert z_id == 0.0
        assert p_id == 1.0

    def test_get_aspect_trend_on_real_shop(self):
        """Verify aspect trend extraction groups by chronological period."""
        db = DatabaseManager()
        trend = get_aspect_trend(scenario_tag="real_shop", period="month", min_n=1, db=db)
        assert len(trend) > 0
        for b in trend:
            assert "period" in b
            assert b["total"] >= b["neg_count"]
            assert b["wilson_ci_low"] <= b["neg_pct"] <= b["wilson_ci_high"]

    def test_detect_trend_alerts_returns_structured_alerts(self):
        """Verify early warning alert engine outputs valid schema."""
        db = DatabaseManager()
        alerts = detect_trend_alerts(
            scenario_tag="real_shop", period="month", min_n=3, min_delta_pp=5.0, db=db
        )
        assert isinstance(alerts, list)
        for al in alerts:
            assert "aspect" in al
            assert al["severity"] in ("HIGH", "MEDIUM")
            assert al["delta_pp"] >= 5.0
            assert "p_value" in al

    def test_platform_comparison_with_ztest(self):
        """Verify platform gap comparison between Shopee and TikTok."""
        db = DatabaseManager()
        comp = get_platform_comparison(scenario_tag="real_shop", min_n=1, db=db)
        assert isinstance(comp, list)
        for c in comp:
            assert "aspect" in c
            assert "shopee_neg_pct" in c
            assert "tiktok_neg_pct" in c
            assert "p_value" in c
            assert isinstance(c["significant"], bool)


# CreBy: MenBoyBMN
