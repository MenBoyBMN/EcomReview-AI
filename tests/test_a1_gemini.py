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
        assert validated.opinions[0].evidence_ok is True
        assert validated.opinions[1].evidence_ok is False

    def test_gemini_model_pool_env_override(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        monkeypatch.delenv("GEMINI_MODEL_POOL", raising=False)
        default_analyzer = A1GeminiAnalyzer(cache_dir=tmp_path, api_key="dummy_key")
        assert default_analyzer.model_id == "gemini-3.5-flash"
        assert default_analyzer.model_pool == [
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
            "gemini-3.1-flash-lite",
        ]

        monkeypatch.setenv("GEMINI_MODEL_POOL", "custom-flash-a,custom-flash-b")
        analyzer = A1GeminiAnalyzer(cache_dir=tmp_path, api_key="dummy_key")
        assert analyzer.model_pool == ["custom-flash-a", "custom-flash-b"]

    def test_real_gemini_api_call_with_cache(self, tmp_path):
        import os

        if os.getenv("RUN_LIVE_API_TESTS") != "1":
            return  # Offline deterministic suite by default
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

    def test_shared_redis_cache_shares_results_across_workers_with_ttl(self, tmp_path):
        class _FakeRedis:
            def __init__(self):
                self.store = {}
                self.ttl_map = {}

            def get(self, key):
                return self.store.get(key)

            def set(self, key, value, ex=None):
                self.store[key] = value
                self.ttl_map[key] = ex
                return True

        fake_redis = _FakeRedis()
        worker_a = A1GeminiAnalyzer(
            cache_dir=tmp_path / "cache_a",
            api_key="dummy_key",
            redis_client=fake_redis,
        )
        worker_b = A1GeminiAnalyzer(
            cache_dir=tmp_path / "cache_b",
            api_key="dummy_key",
            redis_client=fake_redis,
        )

        text = "Áo mưa chống thấm tốt nhưng hơi nóng"
        key = worker_a._compute_cache_key(text)
        worker_a.cache_store.set(
            key,
            {
                "overall_sentiment": "positive",
                "opinions": [
                    {
                        "aspect": "WATERPROOF",
                        "polarity": "positive",
                        "evidence": "chống thấm tốt",
                    }
                ],
                "informative": True,
            },
        )
        assert f"ecomreview:absa:{key}" in fake_redis.store
        assert fake_redis.ttl_map[f"ecomreview:absa:{key}"] >= 60

        # Worker B has empty local disk cache_b, yet gets instant Redis cache hit
        worker_b._client = MagicMock()
        res_b = worker_b.analyze_review(text)
        assert res_b.overall_sentiment == Polarity.POS
        assert res_b.opinions[0].aspect == Aspect.WATERPROOF
        worker_b._client.models.generate_content.assert_not_called()
        assert worker_b.cache_store.stats()["hits_redis"] == 1


# CreBy: MenBoyBMN
