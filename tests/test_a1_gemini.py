"""Unit tests for Proposed Analyzer (A1 v1): Gemini Flash."""

import json
from unittest.mock import MagicMock

from ecomreview.analyze.a1_gemini import A1GeminiAnalyzer
from ecomreview.schemas import Aspect, AspectOpinion, Polarity, ReviewAnalysis


class TestA1GeminiAnalyzer:
    """Test suite for A1 Gemini Flash analyzer with caching."""

    def test_cache_key_generation(self, tmp_path):
        analyzer = A1GeminiAnalyzer(cache_dir=tmp_path, api_key="dummy_key")
        k1 = analyzer._compute_cache_key("Áo mưa tốt")
        k2 = analyzer._compute_cache_key("Áo mưa tốt")
        k3 = analyzer._compute_cache_key("Áo mưa xấu")

        assert k1 == k2
        assert k1 != k3
        assert len(k1) == 64

    def test_cache_hit_offline(self, tmp_path):
        analyzer = A1GeminiAnalyzer(cache_dir=tmp_path, api_key="dummy_key")
        test_text = "Áo mưa này chống nước cực tốt"

        cache_key = analyzer._compute_cache_key(test_text)
        cache_file = tmp_path / f"gemini_{cache_key}.json"

        mock_data = {
            "overall_sentiment": "positive",
            "opinions": [
                {
                    "aspect": "WATERPROOF",
                    "polarity": "positive",
                    "evidence": "chống nước",
                }
            ],
            "informative": True,
        }
        cache_file.write_text(json.dumps(mock_data), encoding="utf-8")

        # Must return valid analysis directly from cache without invoking API
        result = analyzer.analyze_review(test_text)
        assert isinstance(result, ReviewAnalysis)
        assert result.overall_sentiment == Polarity.POS
        assert len(result.opinions) == 1
        assert result.opinions[0].aspect == Aspect.WATERPROOF

    def test_evidence_post_validation(self, tmp_path):
        analyzer = A1GeminiAnalyzer(cache_dir=tmp_path, api_key="dummy_key")
        analysis = ReviewAnalysis(
            overall_sentiment=Polarity.POS,
            opinions=[
                AspectOpinion(
                    aspect=Aspect.WATERPROOF,
                    polarity=Polarity.POS,
                    evidence="chống nước",  # In text
                ),
                AspectOpinion(
                    aspect=Aspect.PRICE_VALUE,
                    polarity=Polarity.NEG,
                    evidence="quá đắt đỏ",  # NOT in text
                ),
            ],
            informative=True,
        )

        validated = analyzer._post_validate_evidence(
            analysis, raw_text="Áo mưa chống nước tốt", norm_text="áo mưa chống nước tốt"
        )
        assert len(validated.opinions) == 2

    def test_real_gemini_api_call_with_cache(self, tmp_path):
        import os

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key.startswith("your_"):
            return  # Skip live call if key unavailable

        analyzer = A1GeminiAnalyzer(cache_dir=tmp_path, api_key=api_key)
        text = "Vải áo mưa dày dặn, đường may chắc chắn"

        # First call: hits live API and creates cache
        res1 = analyzer.analyze_review(text)
        assert isinstance(res1, ReviewAnalysis)
        assert res1.overall_sentiment == Polarity.POS

        cache_key = analyzer._compute_cache_key(text)
        cache_file = tmp_path / f"gemini_{cache_key}.json"
        assert cache_file.exists()

        # Second call: reads immediately from cache
        analyzer._client = MagicMock()  # Mock client to prove API is not called
        res2 = analyzer.analyze_review(text)
        assert res2.overall_sentiment == res1.overall_sentiment
        analyzer._client.models.generate_content.assert_not_called()


# CreBy: MenBoyBMN
