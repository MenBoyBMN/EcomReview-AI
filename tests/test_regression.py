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


def test_fix_wilson_ci_clamped() -> None:
    """Verify wilson_ci_pct clamps k if k > n without crashing or returning NaN."""
    from ecomreview.agent.tools_aggregator import wilson_ci_pct

    low, high = wilson_ci_pct(15, 10)
    assert 0.0 <= low <= high <= 100.0


def test_fix_critic_accepts_both_id_and_insight_id() -> None:
    """Verify HybridCritic checks R1 citing insight properly with either key."""
    from ecomreview.agent.critic import HybridCritic
    from ecomreview.schemas import ActionProposal, ActionType

    critic = HybridCritic()
    insights = [
        {"id": 42, "kind": "ASPECT_COMPLAINT_HIGH", "aspect": "WATERPROOF", "evidence_count": 5}
    ]
    proposal = ActionProposal(
        action_id="act_test",
        action_type=ActionType.PRODUCT_FIX,
        title="Gia cố keo dán ép nhiệt đường may",
        what_to_do="Tăng nhiệt độ máy ép seam tape thêm 15 độ C tại đáy quần.",
        why_rationale="Căn cứ từ phản hồi khách hàng về khía cạnh chống thấm nước.",
        how_and_when="Triển khai tại xưởng trong vòng 48h.",
        success_metric="Giảm 20% phàn nàn thấm nước.",
        insight_ids=[42],
        evidence_review_ids=["rev_1", "rev_2"],
    )
    report = critic.evaluate([proposal], insights, valid_review_ids={"rev_1", "rev_2"})
    # R1: Valid insight IDs cited must pass
    r1_violations = [v for v in report.violations if v.rule_id == "R1"]
    assert len(r1_violations) == 0


def test_planner_strength_fallback_never_returns_product_fix() -> None:
    """STRENGTH insight without matching playbook rule must not fall back to TOP_PAIN."""
    from ecomreview.agent.planner import ActionPlanner

    planner = ActionPlanner(use_llm=False)
    insights = [
        {
            "id": 10,
            "kind": "STRENGTH",
            "aspect": "WATERPROOF",
            "statement": "Khía cạnh chống thấm đạt 95% tích cực.",
            "numbers": {"pos_pct": 95.0, "total": 20},
            "evidence_ids": ["rev_1", "rev_2"],
            "confidence": "HIGH",
        }
    ]
    proposals = planner.generate_proposals(insights, fallback_review_ids=["rev_1", "rev_2"])
    assert len(proposals) == 1
    assert proposals[0].action_type.value == "CONTENT"
    assert proposals[0].is_marketing is True


def test_evidence_selector_emerging_general_excludes_specific_aspect_negatives(tmp_path) -> None:
    """Specific-aspect negative reviews must not be pulled into GENERAL emerging issues."""
    from ecomreview.agent.evidence_selector import get_emerging_general_issues
    from ecomreview.db.database import DatabaseManager

    db = DatabaseManager(tmp_path / "test_emerging.db")
    for i in range(4):
        db.upsert_review_and_opinions(
            review_id=f"wp_neg_{i}",
            platform="shopee",
            shop="shop_a",
            product="ao_mua",
            rating=2,
            text_raw=f"Áo mưa bị thấm nước ở đường may số {i}",
            text_norm=f"áo mưa bị thấm nước ở đường may số {i}",
            source="review",
            scenario_tag="em_scen",
            overall_sentiment="negative",
            informative=True,
            opinions=[{"aspect": "WATERPROOF", "polarity": "negative", "evidence": "thấm nước"}],
        )
    assert get_emerging_general_issues("em_scen", db=db) is None


def test_critic_auto_repair_r7_passes_r2() -> None:
    """Auto-repairing R7 in why_rationale must not inject ungrounded '1-1' numbers."""
    from ecomreview.agent.critic import HybridCritic
    from ecomreview.schemas import ActionProposal, ActionType

    critic = HybridCritic()
    insights = [
        {
            "id": 7,
            "kind": "TOP_PAIN",
            "aspect": "WATERPROOF",
            "numbers": {"total": 20, "neg_count": 10, "neg_pct": 50.0},
        }
    ]
    bad = ActionProposal(
        action_id="act_r7",
        action_type=ActionType.CUSTOMER_CARE,
        title="Hỗ trợ hoàn tiền qua zalo cá nhân",
        what_to_do="Nhắn tin qua zalo cá nhân để xử lý khiếu nại thấm nước.",
        why_rationale="Khách cần hỗ trợ nhanh thay vì zalo cá nhân.",
        how_and_when="Xử lý trong 24h.",
        success_metric="Giảm 20% khiếu nại.",
        insight_ids=[7],
        evidence_review_ids=["r1", "r2"],
    )
    repaired = critic.auto_repair([bad], insights, valid_review_ids={"r1", "r2"})
    rep = critic.evaluate(repaired, insights, valid_review_ids={"r1", "r2"})
    assert rep.passed is True


def test_b1_rule_preserves_verbatim_evidence_with_punctuation() -> None:
    """B1RuleAnalyzer must extract verbatim substrings even when punctuation is present."""
    b1 = B1RuleAnalyzer(enable_norm=True)
    text = "Hàng ok, dùng tạm được, nhưng đường may hơi lỏng!"
    res = b1.analyze_review(text)
    assert len(res.opinions) >= 1
    for op in res.opinions:
        assert op.evidence.lower() in text.lower()


def test_ingest_identical_short_reviews_distinct_ids(tmp_path) -> None:
    """Identical short reviews without explicit review_id must not overwrite each other."""
    from ecomreview.db.database import DatabaseManager
    from ecomreview.ingest_service import ingest_review_batch

    db = DatabaseManager(tmp_path / "test_ingest_dup.db")
    batch = [
        {"platform": "shopee", "rating": 5, "text": "áo đẹp"},
        {"platform": "shopee", "rating": 5, "text": "áo đẹp"},
        {"platform": "tiktok", "rating": 5, "text": "áo đẹp"},
    ]
    res = ingest_review_batch(db, batch, scenario_tag="dup_scen", analyzer_method="b1_rule")
    assert res["inserted_count"] == 3
    with db.get_connection(read_only=True) as conn:
        cnt = conn.execute(
            "SELECT COUNT(*) AS c FROM reviews WHERE scenario_tag = 'dup_scen'"
        ).fetchone()["c"]
    assert cnt == 3


def test_reply_g5_flags_partial_aspect_coverage_and_template_covers_all() -> None:
    """G5 must flag missing negative aspects, while build_template_reply covers 3+ aspects."""
    from ecomreview.agent.reply_assistant import build_template_reply, check_reply_guardrails

    partial = (
        "Dạ Shop xin lỗi về sự cố giao hàng chậm trễ và đóng gói chưa kỹ, "
        "Shop sẽ khắc phục ngay qua kênh Chat của sàn ạ!"
    )
    rep = check_reply_guardrails(partial, negative_aspects=["PACKAGING_SHIPPING", "WATERPROOF"])
    assert rep.passed is False
    assert any("G5" in v for v in rep.violations)

    full_tpl = build_template_reply(
        ["WATERPROOF", "MATERIAL_DURABILITY", "FIT_SIZE", "PACKAGING_SHIPPING"]
    )
    rep_tpl = check_reply_guardrails(
        full_tpl,
        negative_aspects=["WATERPROOF", "MATERIAL_DURABILITY", "FIT_SIZE", "PACKAGING_SHIPPING"],
    )
    assert rep_tpl.passed is True


def test_reply_g2_and_g6_catch_zalo_and_spelled_money() -> None:
    """G2 must block 'zalo cá nhân' even with YAML loaded; G6 must catch '50.000 đồng'/'50 ngàn'."""
    from ecomreview.agent.reply_assistant import check_reply_guardrails

    zalo_msg = (
        "Dạ Shop xin lỗi về sự cố giao hàng chậm trễ, Quý khách nhắn qua zalo cá nhân để Shop "
        "hỗ trợ đổi trả miễn phí ngay qua kênh Chat của sàn ạ!"
    )
    rep_zalo = check_reply_guardrails(zalo_msg, negative_aspects=["PACKAGING_SHIPPING"])
    assert rep_zalo.passed is False
    assert any("G2" in v for v in rep_zalo.violations)

    for money_phrase in ("50.000 đồng", "50 ngàn"):
        money_msg = (
            f"Dạ Shop xin lỗi về sự cố thấm nước, Shop gửi voucher {money_phrase} để hỗ trợ "
            "Quý khách qua cổng Chat chính thức của sàn ạ."
        )
        rep_money = check_reply_guardrails(money_msg, negative_aspects=["WATERPROOF"])
        assert rep_money.passed is False
        assert any("G6" in v for v in rep_money.violations)


def test_critic_r1_rejects_duplicate_evidence_ids() -> None:
    """HybridCritic R1 must require >= 2 distinct evidence_review_ids."""
    from ecomreview.agent.critic import HybridCritic
    from ecomreview.schemas import ActionProposal, ActionType

    critic = HybridCritic()
    insights = [{"id": 1, "kind": "TOP_PAIN", "aspect": "WATERPROOF", "numbers": {"total": 10}}]
    dup_prop = ActionProposal(
        action_id="act_dup",
        action_type=ActionType.PRODUCT_FIX,
        title="Kiểm tra keo dán đường may chống thấm",
        what_to_do="Kiểm tra lại dây chuyền ép seam chống thấm trong 48h.",
        why_rationale="Dựa trên 10 phản hồi của khách hàng.",
        how_and_when="Thực hiện trong 48h.",
        success_metric="Giảm 20% khiếu nại.",
        insight_ids=[1],
        evidence_review_ids=["rev_1", "rev_1"],
    )
    report = critic.evaluate([dup_prop], insights, valid_review_ids={"rev_1", "rev_2"})
    assert report.passed is False
    assert any(v.rule_id == "R1" and "khác nhau" in v.message for v in report.violations)


def test_verify_numbers_standalone_95pct_and_grouped_thousands() -> None:
    """Standalone '95%' and thousands-grouped counts must verify properly."""
    from ecomreview.agent.insight_engine import verify_numbers_in_statement

    stmt = "Mức độ tin cậy 95% với tỷ lệ từ 10.5% đến 20.5% trên tổng 1,000 mẫu."
    assert verify_numbers_in_statement(stmt, {"low": 10.5, "high": 20.5, "total": 1000}) is True


def test_b1_rule_messaging_chat_and_emoji_tokens() -> None:
    """B1RuleAnalyzer must skip messaging 'chat với shop' and score '[EMO_POS]'."""
    b1 = B1RuleAnalyzer(enable_norm=True)
    res_chat = b1.analyze_review("Chất liệu vải dày, chat với shop rất nhiệt tình")
    fit_ops = [op for op in res_chat.opinions if op.aspect == Aspect.FIT_SIZE]
    assert not fit_ops

    res_emo = b1.analyze_review("Áo mưa ổn quá [EMO_POS]")
    assert res_emo.overall_sentiment.value == "positive"


def test_security_sanitize_for_llm_respects_max_chars_after_escape() -> None:
    """sanitize_for_llm must enforce max_chars after HTML escaping."""
    from ecomreview.security import sanitize_for_llm

    raw = "<" * 30
    cleaned = sanitize_for_llm(raw, max_chars=40)
    assert len(cleaned) <= 40


def test_api_validation_and_query_reviews_filtered_by_ids(tmp_path) -> None:
    """Verify early 400 checks and filtering/pagination when review_ids is provided."""
    from fastapi.testclient import TestClient

    from ecomreview.api.main import create_app

    app = create_app(db_path=str(tmp_path / "api_val.db"))
    client = TestClient(app)

    bad_upload = client.post(
        "/api/v1/reviews/upload",
        json={
            "scenario_tag": "val_scen",
            "analyzer_method": "nonexistent_algo",
            "reviews": [{"review_id": "r1", "rating": 5, "text": "Áo đẹp lắm ạ"}],
        },
    )
    assert bad_upload.status_code == 400

    ok_upload = client.post(
        "/api/v1/reviews/upload",
        json={
            "scenario_tag": "val_scen",
            "analyzer_method": "b1_rule",
            "reviews": [
                {"review_id": "r1", "platform": "shopee", "rating": 5, "text": "Áo đẹp lắm"},
                {"review_id": "r2", "platform": "tiktok", "rating": 2, "text": "Thấm nước quá"},
            ],
        },
    )
    assert ok_upload.status_code == 200

    bad_mode = client.post("/api/v1/reviews/r1/reply-draft?scenario_tag=val_scen&mode=invalid")
    assert bad_mode.status_code == 400

    filtered = client.get(
        "/api/v1/reviews",
        params={"scenario_tag": "val_scen", "review_ids": "r1,r2", "platform": "shopee"},
    )
    assert filtered.status_code == 200
    body = filtered.json()
    assert body["total_count"] == 1
    assert [r["review_id"] for r in body["reviews"]] == ["r1"]


def test_get_action_impact_clamps_min_n_and_handles_iso_post_end(tmp_path) -> None:
    """min_n=0 must clamp to >=1 without ZeroDivisionError and include ISO post_end rows."""
    from ecomreview.agent.tools_aggregator import get_action_impact
    from ecomreview.db.database import DatabaseManager

    db = DatabaseManager(tmp_path / "impact_iso.db")
    db.upsert_review_and_opinions(
        review_id="pre_1",
        platform="shopee",
        shop="s",
        product="p",
        rating=2,
        text_raw="Thấm nước",
        text_norm="thấm nước",
        source="review",
        scenario_tag="imp_scen",
        overall_sentiment="negative",
        informative=True,
        opinions=[{"aspect": "WATERPROOF", "polarity": "negative", "evidence": "Thấm nước"}],
        created_at="2026-02-06T08:00:00",
    )
    db.upsert_review_and_opinions(
        review_id="post_1",
        platform="shopee",
        shop="s",
        product="p",
        rating=5,
        text_raw="Không thấm nước nữa",
        text_norm="không thấm nước nữa",
        source="review",
        scenario_tag="imp_scen",
        overall_sentiment="positive",
        informative=True,
        opinions=[{"aspect": "WATERPROOF", "polarity": "positive", "evidence": "Không thấm"}],
        created_at="2026-02-15T18:30:00",
    )
    aid = db.insert_action(
        scenario_tag="imp_scen",
        action_type="PRODUCT_FIX",
        is_marketing=False,
        title="Sửa ép đường may",
        what_to_do="Sửa ép seam tape trong 48h",
        why_rationale="Dữ liệu phàn nàn",
        how_and_when="48h",
        success_metric="Giảm 20%",
        effort="LOW",
        impact="HIGH",
        priority_score=2.5,
        insight_ids=[],
        evidence_review_ids=["pre_1", "post_1"],
        status="APPROVED",
    )
    res = get_action_impact(aid, window_days=5, since="2026-02-10", min_n=0, db=db)
    assert res["pre_window"]["total"] == 1
    assert res["post_window"]["total"] == 1
    assert res["status"] in {"improved", "no_significant_change", "worsened"}


# CreBy: MenBoyBMN
