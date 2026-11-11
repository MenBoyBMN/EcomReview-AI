"""Tests for Customer Care Reply Assistant and G1-G6 Guardrails."""

from ecomreview.agent.reply_assistant import (
    build_template_reply,
    check_reply_guardrails,
    generate_customer_reply,
)
from ecomreview.db.database import DatabaseManager


class TestReplyAssistant:
    """Validate customer care replies satisfy all G1-G6 guardrails."""

    def test_compliant_template_passes_all_guardrails(self):
        """Verify standard template satisfies all G1-G6 rules."""
        text = build_template_reply(["WATERPROOF"], review_id="rev_01")
        report = check_reply_guardrails(text, negative_aspects=["WATERPROOF"])
        assert report.passed
        assert len(report.violations) == 0

    def test_g1_catches_overclaiming(self):
        """Verify G1 flags overclaiming phrases like 'chống thấm 100%'."""
        bad_reply = (
            "Dạ Shop cam kết áo mưa chống thấm 100% tuyệt đối không bao giờ thấm "
            "vào người khi Quý khách đi mưa to ạ!"
        )
        report = check_reply_guardrails(bad_reply, ["WATERPROOF"])
        assert not report.passed
        assert any("G1" in v for v in report.violations)

    def test_g2_catches_policy_bribery(self):
        """Verify G2 flags policy violations like 'tặng tiền đổi 5 sao'."""
        bad_reply = (
            "Dạ Quý khách liên hệ Zalo cá nhân để shop tặng tiền đổi 5 sao "
            "hoặc hoàn tiền nếu sửa đánh giá giúp shop nhé ạ!"
        )
        report = check_reply_guardrails(bad_reply)
        assert not report.passed
        assert any("G2" in v for v in report.violations)

    def test_g3_catches_pii_and_links(self):
        """Verify G3 flags phone numbers, emails, and external links."""
        bad_reply = (
            "Dạ xin liên hệ 0912 345 678 hoặc gửi email support@aomua.vn "
            "hoặc truy cập https://aomua.vn để nhận hỗ trợ bảo hành ạ!"
        )
        report = check_reply_guardrails(bad_reply)
        assert not report.passed
        assert any("G3" in v for v in report.violations)

    def test_g4_catches_short_or_long_replies(self):
        """Verify G4 flags replies outside 40-600 characters."""
        too_short = "Cảm ơn bạn nhé."
        report = check_reply_guardrails(too_short)
        assert not report.passed
        assert any("G4" in v for v in report.violations)

    def test_g6_catches_unauthorized_money_promises(self):
        """Verify G6 flags specific monetary promises like 'đền 50k'."""
        bad_reply = (
            "Dạ Shop xin lỗi Quý khách về sự cố và xin phép hoàn tiền 50k "
            "vào ví của Quý khách ngay hôm nay ạ!"
        )
        report = check_reply_guardrails(bad_reply)
        assert not report.passed
        assert any("G6" in v for v in report.violations)

    def test_generate_customer_reply_end_to_end(self, tmp_path):
        """Verify generate_customer_reply reads DB and returns compliant draft."""
        db_file = tmp_path / "test_reply.db"
        db = DatabaseManager(db_path=str(db_file), db_backend="sqlite")

        db.upsert_review_and_opinions(
            review_id="r_neg_01",
            platform="shopee",
            shop="shop_a",
            product="ao_mua",
            rating=1,
            text_raw="Áo mưa bị rò nước đường may ướt hết người",
            text_norm="ao mua bi ro nuoc duong may uot het nguoi",
            source="review",
            scenario_tag="test_scen",
            overall_sentiment="negative",
            informative=True,
            opinions=[{"aspect": "WATERPROOF", "polarity": "negative", "evidence": "ro nuoc"}],
            analyzer_method="b1_rule",
        )

        res = generate_customer_reply("r_neg_01", scenario_tag="test_scen", mode="template", db=db)
        assert res["review_id"] == "r_neg_01"
        assert res["guardrail_report"]["passed"]
        assert len(res["reply_text"]) >= 40


# CreBy: MenBoyBMN
