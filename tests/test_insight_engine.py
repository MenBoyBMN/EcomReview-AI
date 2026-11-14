"""Unit tests for Week 5 Insight Engine & Numeric Grounding Verifier."""

from ecomreview.agent.insight_engine import InsightEngine, verify_numbers_in_statement
from ecomreview.db.database import DatabaseManager
from ecomreview.schemas import InsightStatement


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

    def test_insight_llm_mode_accepts_grounded_and_rejects_hallucinated(self, tmp_path):
        db = DatabaseManager(tmp_path / "test_ins_llm.db")
        for i in range(6):
            pol = "negative" if i < 3 else "positive"
            db.upsert_review_and_opinions(
                review_id=f"shp_{i:04d}",
                platform="shopee",
                shop="shop_a",
                product="ao_mua",
                rating=2 if i < 3 else 5,
                text_raw=f"Đánh giá {i} về khả năng chống thấm nước của áo mưa",
                text_norm=f"đánh giá {i} về khả năng chống thấm nước của áo mưa",
                source="review",
                scenario_tag="llm_scen",
                overall_sentiment=pol,
                informative=True,
                opinions=[{"aspect": "WATERPROOF", "polarity": pol, "evidence": "chống thấm nước"}],
            )

        class _GroundedLLM:
            def generate_structured(self, prompt, schema_cls, system_instruction=""):
                return InsightStatement(
                    statement=(
                        "Khía cạnh chống thấm nước ghi nhận 3/6 phản hồi phàn nàn "
                        "(50.0%, khoảng tin cậy 95% CI 18.8% đến 81.2%)."
                    )
                )

        engine_ok = InsightEngine(db=db, llm_client=_GroundedLLM(), use_llm=True)
        ins_ok = engine_ok.generate_insights(scenario_tag="llm_scen", min_n=5, persist=False)
        assert any(i.get("statement_source") == "llm" for i in ins_ok)

        class _HallucinatingLLM:
            def generate_structured(self, prompt, schema_cls, system_instruction=""):
                return InsightStatement(
                    statement="Có tới 99.9% khách hàng trong tổng số 500 người phàn nàn."
                )

        engine_bad = InsightEngine(db=db, llm_client=_HallucinatingLLM(), use_llm=True)
        ins_bad = engine_bad.generate_insights(scenario_tag="llm_scen", min_n=5, persist=False)
        assert all(i.get("statement_source") == "template" for i in ins_bad)
        for ins in ins_bad:
            assert verify_numbers_in_statement(ins["statement"], ins["numbers"]) is True


# CreBy: MenBoyBMN
