"""Tests for ABSA analyzer factory and fast circuit-breaker fallback."""

import pytest

from ecomreview.analyze.a1_gemini import A1GeminiAnalyzer
from ecomreview.analyze.b1_rule import B1RuleAnalyzer
from ecomreview.analyze.factory import SUPPORTED_METHODS, get_analyzer


class TestAnalyzerFactory:
    """Validate analyzer instantiation, method resolution, and fallback speed."""

    def test_factory_resolves_b1_rule(self):
        """Verify factory resolves b1_rule to B1RuleAnalyzer."""
        analyzer = get_analyzer("b1_rule")
        assert isinstance(analyzer, B1RuleAnalyzer)

    def test_factory_resolves_a1_gemini(self):
        """Verify factory resolves a1_gemini_v2 to A1GeminiAnalyzer."""
        analyzer = get_analyzer("a1_gemini_v2")
        assert isinstance(analyzer, A1GeminiAnalyzer)

    def test_factory_rejects_unknown_method(self):
        """Verify unsupported analyzer raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported analyzer_method"):
            get_analyzer("unknown_deep_learning_model")

    def test_supported_methods_tuple(self):
        """Ensure all canonical methods are listed in SUPPORTED_METHODS."""
        assert "b1_rule" in SUPPORTED_METHODS
        assert "a1_gemini_v2" in SUPPORTED_METHODS

    def test_a1_fast_fallback_without_api_key(self, monkeypatch):
        """Verify A1 immediately falls back to B1 without network latency when no key is present."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        analyzer = A1GeminiAnalyzer(api_key=None)

        res = analyzer.analyze_review("Áo mưa bị rách đường may")
        assert res is not None
        assert res.overall_sentiment.value in ("negative", "neutral", "positive")
        assert len(res.opinions) >= 1


# CreBy: MenBoyBMN
