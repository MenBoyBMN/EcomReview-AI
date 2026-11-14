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

    def _seed_trend_db(self, tmp_path):
        db = DatabaseManager(tmp_path / "test_trends.db")
        # Baseline month 2026-08: 1/6 negative (16.7%)
        for i in range(6):
            pol = "negative" if i == 0 else "positive"
            db.upsert_review_and_opinions(
                review_id=f"tr_aug_{i}",
                platform="shopee" if i % 2 == 0 else "tiktok",
                shop="shop_a",
                product="ao_mua",
                rating=2 if pol == "negative" else 5,
                text_raw=f"Đánh giá tháng 8 số {i} về chống thấm nước",
                text_norm=f"đánh giá tháng 8 số {i} về chống thấm nước",
                source="review",
                scenario_tag="trend_scen",
                overall_sentiment=pol,
                informative=True,
                opinions=[{"aspect": "WATERPROOF", "polarity": pol, "evidence": "chống thấm"}],
                created_at=f"2026-08-0{i + 1}",
            )
        # Latest month 2026-09: 5/6 negative (83.3%) -> delta +66.6pp
        for i in range(6):
            pol = "negative" if i < 5 else "positive"
            db.upsert_review_and_opinions(
                review_id=f"tr_sep_{i}",
                platform="shopee" if i < 4 else "tiktok",
                shop="shop_a",
                product="ao_mua",
                rating=1 if pol == "negative" else 5,
                text_raw=f"Đánh giá tháng 9 số {i} về chống thấm nước",
                text_norm=f"đánh giá tháng 9 số {i} về chống thấm nước",
                source="review",
                scenario_tag="trend_scen",
                overall_sentiment=pol,
                informative=True,
                opinions=[{"aspect": "WATERPROOF", "polarity": pol, "evidence": "chống thấm"}],
                created_at=f"2026-09-0{i + 1}",
            )
        return db

    def test_get_aspect_trend_on_real_shop(self, tmp_path):
        """Verify aspect trend extraction groups by chronological period."""
        db = self._seed_trend_db(tmp_path)
        trend = get_aspect_trend(scenario_tag="trend_scen", period="month", min_n=1, db=db)
        assert len(trend) == 2
        for b in trend:
            assert "period" in b
            assert "pos_pct" in b
            assert b["total"] >= b["neg_count"]
            assert b["wilson_ci_low"] <= b["neg_pct"] <= b["wilson_ci_high"]

    def test_detect_trend_alerts_returns_structured_alerts(self, tmp_path):
        """Verify early warning alert engine outputs valid schema."""
        db = self._seed_trend_db(tmp_path)
        alerts = detect_trend_alerts(
            scenario_tag="trend_scen", period="month", min_n=3, min_delta_pp=5.0, db=db
        )
        assert len(alerts) >= 1
        for al in alerts:
            assert "aspect" in al
            assert al["severity"] in ("HIGH", "MEDIUM")
            assert al["delta_pp"] >= 5.0
            assert "p_value" in al

    def test_platform_comparison_with_ztest(self, tmp_path):
        """Verify platform gap comparison between Shopee and TikTok."""
        db = self._seed_trend_db(tmp_path)
        comp = get_platform_comparison(scenario_tag="trend_scen", min_n=1, db=db)
        assert len(comp) >= 1
        for c in comp:
            assert "aspect" in c
            assert "shopee_neg_pct" in c
            assert "tiktok_neg_pct" in c
            assert "p_value" in c
            assert isinstance(c["significant"], bool)


# CreBy: MenBoyBMN
