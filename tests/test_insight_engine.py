"""Unit tests for Week 5 Insight Engine & Numeric Grounding Verifier."""

from ecomreview.agent.insight_engine import InsightEngine, verify_numbers_in_statement
from ecomreview.db.database import DatabaseManager


class TestInsightEngine:
    """Test suite for verify_numbers_in_statement and InsightEngine."""

    def test_verify_numbers_accepts_grounded_and_benign(self):
        allowed = {
            "neg_count": 12,
            "total": 35,
            "neg_pct": 34.3,
            "ci_low": 20.8,
            "ci_high": 50.9,
        }
        stmt = (
            "Trong tổng số 35 đánh giá (bao gồm cả nhóm 5 sao như mã tts_0144), "
            "có 12 ý kiến phàn nàn (34.3%, khoảng tin cậy 95% CI từ 20.8% đến 50.9%)."
        )
        assert verify_numbers_in_statement(stmt, allowed) is True

    def test_verify_numbers_rejects_hallucinated_numbers(self):
        allowed = {"neg_count": 12, "total": 35, "neg_pct": 34.3}
        # 48.5% is hallucinated
        bad_stmt = "Trong 35 đánh giá, có tới 48.5% khách hàng phàn nàn về chống thấm."
        assert verify_numbers_in_statement(bad_stmt, allowed) is False

    def test_generate_and_persist_insights(self, tmp_path):
        db = DatabaseManager(tmp_path / "test_insights.db")
        for i in range(10):
            pol = "negative" if i < 3 else "positive"
            db.upsert_review_and_opinions(
                review_id=f"tts_{i:04d}",
                platform="tiktok" if i < 6 else "shopee",
                shop="shop_a",
                product="ao_mua_da_ca",
                rating=5 if i >= 2 else 2,
                text_raw=f"Đánh giá số {i} về chất liệu vải da cá và khả năng chống thấm nước",
                text_norm=f"đánh giá số {i} về chất liệu vải da cá và khả năng chống thấm nước",
                source="review",
                scenario_tag="real_shop",
                overall_sentiment=pol,
                informative=True,
                opinions=[
                    {"aspect": "WATERPROOF", "polarity": pol, "evidence": "chống thấm nước"},
                    {
                        "aspect": "MATERIAL_DURABILITY",
                        "polarity": "positive",
                        "evidence": "vải da cá",
                    },
                ],
            )

        engine = InsightEngine(db=db)
        insights = engine.generate_insights(scenario_tag="real_shop", min_n=5, persist=True)
        assert len(insights) >= 3
        for ins in insights:
            assert verify_numbers_in_statement(ins["statement"], ins["numbers"]) is True
            assert len(ins["evidence_ids"]) >= 2


# CreBy: MenBoyBMN
