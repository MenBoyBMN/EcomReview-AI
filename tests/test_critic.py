"""Unit tests for Week 6 HybridCritic (10 Fault-Injection Scenarios across R1-R7) & State-Graph."""

from ecomreview.agent.critic import HybridCritic
from ecomreview.agent.graph_runner import EcomReviewGraphRunner
from ecomreview.db.database import DatabaseManager
from ecomreview.schemas import ActionProposal, ActionType

SAMPLE_INSIGHTS = [
    {
        "insight_id": 1,
        "kind": "TOP_PAIN",
        "aspect": "WATERPROOF",
        "statement": (
            "Điểm đau cốt lõi ở WATERPROOF: Trong 20 phản hồi, có 10 ý kiến phàn nàn "
            "(50.0%, khoảng tin cậy 95% CI từ 29.9% đến 70.1%)."
        ),
        "numbers": {
            "total": 20,
            "neg_count": 10,
            "neg_pct": 50.0,
            "ci_low": 29.9,
            "ci_high": 70.1,
        },
        "evidence_ids": ["tts_0001", "tts_0002", "tts_0003"],
        "confidence": "HIGH",
    },
    {
        "insight_id": 2,
        "kind": "TOP_PAIN",
        "aspect": "MATERIAL_DURABILITY",
        "statement": (
            "Điểm đau cốt lõi ở MATERIAL_DURABILITY: Trong 40 phản hồi, có 12 ý kiến phàn nàn "
            "(30.0%, khoảng tin cậy 95% CI từ 18.1% đến 45.4%)."
        ),
        "numbers": {
            "total": 40,
            "neg_count": 12,
            "neg_pct": 30.0,
            "ci_low": 18.1,
            "ci_high": 45.4,
        },
        "evidence_ids": ["tts_0004", "tts_0005", "tts_0006"],
        "confidence": "HIGH",
    },
]

VALID_REVIEW_IDS = {"tts_0001", "tts_0002", "tts_0003", "tts_0004", "tts_0005", "tts_0006"}


def _make_valid_proposal(action_id: str = "act_001") -> ActionProposal:
    return ActionProposal(
        action_id=action_id,
        action_type=ActionType.PRODUCT_FIX,
        is_marketing=False,
        title="Gia cố băng keo ép nhiệt đường may đáy quần áo mưa",
        what_to_do="Tăng nhiệt độ ép seam tape PVC tại đường may đáy quần và nẹp khóa kéo.",
        why_rationale=(
            "Căn cứ từ dữ liệu: Trong 20 phản hồi, có 10 ý kiến phàn nàn "
            "(50.0%, khoảng tin cậy 95% CI từ 29.9% đến 70.1%)."
        ),
        how_and_when="Kiểm định ngẫu nhiên 20 mẫu tại xưởng trong vòng 48h.",
        success_metric="Giảm tỷ lệ phàn nàn thấm nước xuống dưới 15% trong 14 ngày.",
        effort="HIGH",
        impact="HIGH",
        priority_score=3.2,
        insight_ids=[1],
        evidence_review_ids=["tts_0001", "tts_0002"],
    )


class TestHybridCriticTenFaults:
    """Verify that HybridCritic catches 10/10 injected faults across R1-R7."""

    def setup_method(self):
        self.critic = HybridCritic()

    def test_valid_proposal_passes_all_rules(self):
        p = _make_valid_proposal()
        report = self.critic.evaluate([p], SAMPLE_INSIGHTS, VALID_REVIEW_IDS)
        assert report.passed is True
        assert report.score == 5.0
        assert len(report.violations) == 0

    def test_10_fault_injected_proposals_caught_100_percent(self):
        """Inject 10 distinct faults covering R1-R7 and verify 10/10 detection."""
        # Fault 1 (R1): Non-existent insight_id (999)
        f1 = _make_valid_proposal("f1")
        f1.insight_ids = [999]

        # Fault 2 (R1): Unknown/fabricated evidence_review_id
        f2 = _make_valid_proposal("f2")
        f2.evidence_review_ids = ["fake_rev_999", "fake_rev_888"]

        # Fault 3 (R2): Hallucinated percentage in why_rationale (87.5% instead of 50.0%)
        f3 = _make_valid_proposal("f3")
        f3.why_rationale = "Trong 20 phản hồi, có tới 87.5% khách hàng phàn nàn bị thấm nước."

        # Fault 4 (R2): Hallucinated count in why_rationale (95/100 instead of 10/20)
        f4 = _make_valid_proposal("f4")
        f4.why_rationale = "Có 95 trên 100 khách hàng đánh giá áo mưa bị rách đường may."

        # Fault 5 (R3): Missing deadline keyword in how_and_when
        f5 = _make_valid_proposal("f5")
        f5.how_and_when = "Triển khai thực hiện tại xưởng sản xuất khi thuận tiện."

        # Fault 6 (R3): Incomplete/too-short what_to_do field
        f6 = _make_valid_proposal("f6")
        f6.what_to_do = "Sửa lỗi."
        f6.description = "Sửa lỗi."

        # Fault 7 (R4): Overclaiming "chống thấm 100%" on WATERPROOF
        f7 = _make_valid_proposal("f7")
        f7.title = "Cam kết áo mưa chống thấm 100% dưới mọi cơn bão"

        # Fault 8 (R5): Marketing flag desynchronized (PRODUCT_FIX with is_marketing=True)
        f8 = _make_valid_proposal("f8")
        f8.action_type = ActionType.PRODUCT_FIX
        f8.is_marketing = True

        # Fault 9 (R6): Near-duplicate proposals (Jaccard > 0.80)
        f9_a = _make_valid_proposal("f9_a")
        f9_b = _make_valid_proposal("f9_b")

        # Fault 10 (R7): Prohibited platform policy bribery ("tặng tiền đổi 5 sao")
        f10 = _make_valid_proposal("f10")
        f10.what_to_do = "Nhắn tin Zalo cho khách để tặng tiền đổi 5 sao và xóa đánh giá 1 sao."

        single_fault_cases = [
            (f1, "R1"),
            (f2, "R1"),
            (f3, "R2"),
            (f4, "R2"),
            (f5, "R3"),
            (f6, "R3"),
            (f7, "R4"),
            (f8, "R5"),
            (f10, "R7"),
        ]

        caught_count = 0
        for prop, expected_rule in single_fault_cases:
            rep = self.critic.evaluate([prop], SAMPLE_INSIGHTS, VALID_REVIEW_IDS)
            rule_ids = {v.rule_id for v in rep.violations}
            assert not rep.passed, f"Expected {prop.action_id} to fail"
            assert expected_rule in rule_ids, f"Expected {expected_rule} in {rule_ids}"
            caught_count += 1

        # Evaluate Fault 9 pair (R6 duplication)
        rep_dup = self.critic.evaluate([f9_a, f9_b], SAMPLE_INSIGHTS, VALID_REVIEW_IDS)
        assert not rep_dup.passed
        assert "R6" in {v.rule_id for v in rep_dup.violations}
        caught_count += 1

        assert caught_count == 10

    def test_auto_repair_fixes_all_faults(self):
        f_bad = _make_valid_proposal("act_bad")
        f_bad.insight_ids = [999]
        f_bad.evidence_review_ids = ["fake_01", "fake_02"]
        f_bad.why_rationale = "Có 99% khách phàn nàn."
        f_bad.how_and_when = "Làm sớm"
        f_bad.title = "Quảng cáo chống thấm 100% và tặng tiền đổi 5 sao"
        f_bad.is_marketing = True  # Wrong for PRODUCT_FIX

        repaired = self.critic.auto_repair([f_bad], SAMPLE_INSIGHTS, VALID_REVIEW_IDS)
        rep = self.critic.evaluate(repaired, SAMPLE_INSIGHTS, VALID_REVIEW_IDS)
        assert rep.passed is True
        assert len(rep.violations) == 0

    def test_state_graph_runner_end_to_end(self, tmp_path):
        db = DatabaseManager(tmp_path / "test_graph.db")
        for i in range(10):
            pol = "negative" if i < 6 else "positive"
            db.upsert_review_and_opinions(
                review_id=f"tts_{i:04d}",
                platform="tiktok" if i < 5 else "shopee",
                shop="shop_a",
                product="ao_mua_da_ca",
                rating=2 if i < 6 else 5,
                text_raw=f"Đánh giá số {i} đường may bị thấm nước mưa",
                text_norm=f"đánh giá số {i} đường may bị thấm nước mưa",
                source="review",
                scenario_tag="S_test",
                overall_sentiment=pol,
                informative=True,
                opinions=[{"aspect": "WATERPROOF", "polarity": pol, "evidence": "thấm nước mưa"}],
            )

        runner = EcomReviewGraphRunner(db=db, max_retries=2, trace_dir=tmp_path / "traces")
        res = runner.run_scenario(scenario_tag="S_test", min_n=5)
        assert res["final_critic_passed"] is True
        assert res["actions_count"] >= 1
        assert (tmp_path / "traces" / "trace_S_test.json").exists()


# CreBy: MenBoyBMN
