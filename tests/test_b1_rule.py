"""Unit tests for B1RuleAnalyzer multi-word phrase matching."""

from ecomreview.analyze.b1_rule import B1RuleAnalyzer
from ecomreview.schemas import Aspect, Polarity


class TestB1RulePhrases:
    """Verify multi-word sentiment phrases (2-gram / 3-gram) are matched properly."""

    def test_positive_two_word_phrase_matched(self):
        b1 = B1RuleAnalyzer(enable_norm=True)
        res = b1.analyze_review("Chất liệu vải rất hài lòng, giá cả hợp lý")
        by_aspect = {op.aspect: op.polarity for op in res.opinions}
        assert by_aspect.get(Aspect.MATERIAL_DURABILITY) == Polarity.POS
        assert by_aspect.get(Aspect.PRICE_VALUE) == Polarity.POS

    def test_negated_two_word_phrase_inverts_polarity(self):
        b1 = B1RuleAnalyzer(enable_norm=True)
        res = b1.analyze_review("Chất liệu áo mưa không hài lòng chút nào")
        by_aspect = {op.aspect: op.polarity for op in res.opinions}
        assert by_aspect.get(Aspect.MATERIAL_DURABILITY) == Polarity.NEG

    def test_negative_two_word_phrase_matched(self):
        b1 = B1RuleAnalyzer(enable_norm=True)
        res = b1.analyze_review("Đóng gói và giao hàng quá thất vọng")
        by_aspect = {op.aspect: op.polarity for op in res.opinions}
        assert by_aspect.get(Aspect.PACKAGING_SHIPPING) == Polarity.NEG


# CreBy: MenBoyBMN
