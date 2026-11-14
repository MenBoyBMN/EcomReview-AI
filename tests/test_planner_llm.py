"""Unit tests for LLM-backed ActionPlanner with deterministic guardrails and GraphRunner."""

from ecomreview.agent.graph_runner import EcomReviewGraphRunner
from ecomreview.agent.planner import ActionPlanner
from ecomreview.db.database import DatabaseManager
from ecomreview.schemas import ActionPlanBatch, ActionProposal, ActionType, InsightStatement


class _FakeAgentLLM:
    """Fake LLM returning ActionPlanBatch and InsightStatement while recording prompts."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.plan_calls = 0

    def generate_structured(self, prompt, schema_cls, system_instruction="", **kwargs):
        self.prompts.append(prompt)
        if schema_cls is InsightStatement:
            return InsightStatement(
                statement=(
                    "Khía cạnh chống thấm nước ghi nhận 4/6 phản hồi tiêu cực "
                    "(66.7%, khoảng tin cậy 95% CI từ 30.0% đến 90.3%)."
                )
            )
        if schema_cls is ActionPlanBatch:
            self.plan_calls += 1
            # Inject intentional flaws (wrong is_marketing, bad evidence ID, missing deadline)
            # to prove deterministic post-processing repairs them cleanly.
            return ActionPlanBatch(
                proposals=[
                    ActionProposal(
                        action_id="llm_1",
                        action_type=ActionType.PRODUCT_FIX,
                        is_marketing=True,  # Intentionally wrong for PRODUCT_FIX
                        title="Nâng cấp ép seam nhiệt đường may đáy quần",
                        what_to_do="Tăng kiểm tra áp lực máy ép đường may đáy quần theo lô.",
                        why_rationale="Có tới 99% khách bị ướt.",  # Hallucinated -> must fallback
                        how_and_when="Triển khai kiểm tra tại xưởng sản xuất",  # Missing deadline
                        success_metric="Giảm 25% phàn nàn thấm nước trong 14 ngày.",
                        effort="MEDIUM",
                        impact="HIGH",
                        priority_score=999.0,  # Must be recomputed deterministically
                        insight_ids=[9999],  # Invalid -> must fallback to valid insight_id
                        evidence_review_ids=["fake_999", "rev_000"],
                    )
                ]
            )
        raise ValueError(f"Unexpected schema {schema_cls}")


class TestActionPlannerLLM:
    """Validate LLM ActionPlanner integration, post-validation, and GraphRunner trace."""

    def test_planner_llm_refines_and_enforces_guardrails(self):
        fake_llm = _FakeAgentLLM()
        planner = ActionPlanner(llm_client=fake_llm, use_llm=True)
        insights = [
            {
                "insight_id": 1,
                "kind": "TOP_PAIN",
                "aspect": "WATERPROOF",
                "confidence": "HIGH",
                "statement": (
                    "Điểm đau cốt lõi ở khía cạnh WATERPROOF: 4/6 phản hồi phàn nàn "
                    "(66.7%, 95% CI 30.0%-90.3%)."
                ),
                "numbers": {
                    "total": 6,
                    "neg_count": 4,
                    "neg_pct": 66.7,
                    "ci_low": 30.0,
                    "ci_high": 90.3,
                },
                "evidence_ids": ["rev_000", "rev_001"],
            }
        ]
        proposals = planner.generate_proposals(
            insights=insights,
            fallback_review_ids=["rev_000", "rev_001", "rev_002"],
            critic_feedback="R4: tránh overclaim",
            max_actions=3,
        )
        assert len(proposals) == 1
        p = proposals[0]
        assert p.is_marketing is False
        assert p.insight_ids == [1]
        assert "fake_999" not in p.evidence_review_ids
        assert len(p.evidence_review_ids) >= 2
        assert "99%" not in p.why_rationale
        assert "48h" in p.how_and_when
        assert p.priority_score < 10.0
        assert any("R4: tránh overclaim" in pr for pr in fake_llm.prompts)

    def test_graph_runner_records_llm_planner_mode(self, tmp_path):
        db = DatabaseManager(tmp_path / "test_llm_graph.db")
        for i in range(6):
            pol = "negative" if i < 4 else "positive"
            db.upsert_review_and_opinions(
                review_id=f"rev_{i:03d}",
                platform="shopee",
                shop="shop_a",
                product="ao_mua",
                rating=2 if i < 4 else 5,
                text_raw=f"Đánh giá {i} về khả năng chống thấm nước đường may áo mưa",
                text_norm=f"đánh giá {i} về khả năng chống thấm nước đường may áo mưa",
                source="review",
                scenario_tag="llm_graph",
                overall_sentiment=pol,
                informative=True,
                opinions=[{"aspect": "WATERPROOF", "polarity": pol, "evidence": "chống thấm nước"}],
            )

        fake_llm = _FakeAgentLLM()
        runner = EcomReviewGraphRunner(
            db=db,
            trace_dir=tmp_path / "traces",
            use_llm=True,
            llm_client=fake_llm,
        )
        trace = runner.run_scenario(scenario_tag="llm_graph", min_n=5, max_actions=3)
        assert trace["planner_mode"] == "llm"
        assert trace["final_critic_passed"] is True
        assert trace["actions_count"] >= 1


# CreBy: MenBoyBMN
