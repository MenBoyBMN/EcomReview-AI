"""Unit tests for Week 5 Aggregator & Wilson 95% CI Tools."""

from ecomreview.agent.tools_aggregator import (
    get_aspect_sentiment_stats,
    get_hidden_complaints,
    get_platform_gap_stats,
    get_reviews_by_aspect,
    wilson_ci_pct,
)
from ecomreview.db.database import DatabaseManager


class TestAggregatorTools:
    """Test suite for Wilson CI and Read-Only SQL Aggregator tools."""

    def test_wilson_ci_pct_bounds(self):
        # Empty sample returns (0.0, 0.0)
        assert wilson_ci_pct(0, 0) == (0.0, 0.0)

        # 50% on n=100 has symmetric CI around 50%
        low, high = wilson_ci_pct(50, 100)
        assert 40.0 <= low < 50.0
        assert 50.0 < high <= 60.0

        # Small sample n=5, k=5: asymmetric CI below 100%
        low_s, high_s = wilson_ci_pct(5, 5)
        assert 50.0 < low_s < 70.0
        assert high_s == 100.0

    def test_min_n_threshold_and_stats(self, tmp_path):
        db = DatabaseManager(tmp_path / "test_agg.db")

        # Insert 6 WATERPROOF reviews (4 neg, 2 pos) and 3 FIT_SIZE reviews (below min_n=5)
        for i in range(6):
            pol = "negative" if i < 4 else "positive"
            rating = 2 if i < 4 else 5
            db.upsert_review_and_opinions(
                review_id=f"r_wp_{i}",
                platform="shopee" if i < 3 else "tiktok",
                shop="shop_a",
                product="ao_mua",
                rating=rating,
                text_raw=f"Áo mưa mẫu số {i} đánh giá chống nước",
                text_norm=f"áo mưa mẫu số {i} đánh giá chống nước",
                source="review",
                scenario_tag="test_scen",
                overall_sentiment=pol,
                informative=True,
                opinions=[{"aspect": "WATERPROOF", "polarity": pol, "evidence": "chống nước"}],
            )

        for j in range(3):
            db.upsert_review_and_opinions(
                review_id=f"r_sz_{j}",
                platform="tiktok",
                shop="shop_a",
                product="ao_mua",
                rating=5,
                text_raw="Mặc vừa vặn lắm",
                text_norm="mặc vừa vặn lắm",
                source="review",
                scenario_tag="test_scen",
                overall_sentiment="positive",
                informative=True,
                opinions=[{"aspect": "FIT_SIZE", "polarity": "positive", "evidence": "vừa vặn"}],
            )

        stats = get_aspect_sentiment_stats(scenario_tag="test_scen", min_n=5, db=db)
        assert len(stats) == 1
        assert stats[0]["aspect"] == "WATERPROOF"
        assert stats[0]["total"] == 6
        assert stats[0]["neg_count"] == 4
        assert stats[0]["pos_count"] == 2
        assert stats[0]["confidence"] == "low"

        revs = get_reviews_by_aspect(
            scenario_tag="test_scen", aspect="WATERPROOF", polarity="negative", db=db
        )
        assert len(revs) == 4

    def test_hidden_complaints_and_platform_gap(self, tmp_path):
        db = DatabaseManager(tmp_path / "test_gap.db")

        # 5 Shopee reviews on MATERIAL_DURABILITY: 4 negative (80%)
        for i in range(5):
            pol = "negative" if i < 4 else "positive"
            db.upsert_review_and_opinions(
                review_id=f"shp_{i}",
                platform="shopee",
                shop="shop_a",
                product="ao_mua",
                rating=5,  # 5 stars but negative opinion -> hidden complaint!
                text_raw="Giao nhanh nhưng vải hơi mỏng",
                text_norm="giao nhanh nhưng vải hơi mỏng",
                source="review",
                scenario_tag="gap_scen",
                overall_sentiment="positive",
                informative=True,
                opinions=[
                    {"aspect": "MATERIAL_DURABILITY", "polarity": pol, "evidence": "vải hơi mỏng"}
                ],
            )

        # 5 TikTok reviews on MATERIAL_DURABILITY: 0 negative (0%)
        for i in range(5):
            db.upsert_review_and_opinions(
                review_id=f"tts_{i}",
                platform="tiktok",
                shop="shop_a",
                product="ao_mua",
                rating=5,
                text_raw="Chất vải dày dặn rất đẹp",
                text_norm="chất vải dày dặn rất đẹp",
                source="review",
                scenario_tag="gap_scen",
                overall_sentiment="positive",
                informative=True,
                opinions=[
                    {"aspect": "MATERIAL_DURABILITY", "polarity": "positive", "evidence": "dày dặn"}
                ],
            )

        hidden = get_hidden_complaints(scenario_tag="gap_scen", db=db)
        assert len(hidden) == 4

        gaps = get_platform_gap_stats(scenario_tag="gap_scen", min_n=5, db=db)
        assert len(gaps) == 1
        assert gaps[0]["aspect"] == "MATERIAL_DURABILITY"
        assert gaps[0]["gap_pct"] == 80.0


# CreBy: MenBoyBMN
