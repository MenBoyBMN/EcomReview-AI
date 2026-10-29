"""Unit tests for Baseline 1 (B1): Rule and Lexicon Analyzer."""

import time

from ecomreview.analyze.b1_rule import B1RuleAnalyzer
from ecomreview.schemas import Aspect, Polarity, ReviewAnalysis


class TestB1RuleAnalyzer:
    """Test suite for rule-based ABSA analyzer."""

    def setup_method(self):
        self.analyzer = B1RuleAnalyzer()

    def test_waterproof_negation_inversion(self):
        # "không bị thấm" should be positive for waterproof
        text = "Mưa to đi đường xa không bị thấm nước, rất ưng ý"
        result = self.analyzer.analyze_review(text)

        assert isinstance(result, ReviewAnalysis)
        assert result.overall_sentiment == Polarity.POS

        waterproof_ops = [op for op in result.opinions if op.aspect == Aspect.WATERPROOF]
        assert len(waterproof_ops) == 1
        assert waterproof_ops[0].polarity == Polarity.POS
        assert "thấm" in waterproof_ops[0].evidence.lower()

    def test_material_durability_negative(self):
        text = "Chất vải quá mỏng, mới mặc 2 lần đã bị rách"
        result = self.analyzer.analyze_review(text)

        assert result.overall_sentiment == Polarity.NEG
        mat_ops = [op for op in result.opinions if op.aspect == Aspect.MATERIAL_DURABILITY]
        assert len(mat_ops) >= 1
        assert mat_ops[0].polarity == Polarity.NEG

    def test_multi_aspect_sentence(self):
        text = "Áo form rộng thoải mái, nhưng giao hàng hơi chậm"
        result = self.analyzer.analyze_review(text)

        aspects = {op.aspect for op in result.opinions}
        assert Aspect.FIT_SIZE in aspects or Aspect.COMFORT_USABILITY in aspects
        assert Aspect.PACKAGING_SHIPPING in aspects

        shipping_op = next(op for op in result.opinions if op.aspect == Aspect.PACKAGING_SHIPPING)
        assert shipping_op.polarity == Polarity.NEG

    def test_fallback_to_general(self):
        text = "Sản phẩm xài được"
        result = self.analyzer.analyze_review(text)

        assert len(result.opinions) == 1
        assert result.opinions[0].aspect == Aspect.GENERAL
        assert result.opinions[0].polarity == Polarity.POS

    def test_empty_string_handling(self):
        result = self.analyzer.analyze_review("")
        assert result.informative is False
        assert len(result.opinions) == 0

    def test_inference_speed_benchmark(self):
        samples = [
            "Áo chống thấm nước rất tốt, giá cả hợp lý",
            "Màu đẹp, form vừa vặn, giao hàng nhanh",
            "Vải mỏng dễ rách, đường may cẩu thả",
            "Không hài lòng chút nào",
        ] * 20  # 80 reviews

        start = time.perf_counter()
        results = self.analyzer.analyze_batch(samples)
        elapsed = time.perf_counter() - start

        assert len(results) == 80
        # Must execute within 0.15 seconds for 80 reviews
        assert elapsed < 0.15, f"Execution too slow: {elapsed:.4f}s"


# CreBy: MenBoyBMN
