"""Unit tests for Baseline 2 (B2): TF-IDF + Logistic Regression."""

from pathlib import Path

from ecomreview.analyze.b2_tfidf import B2TfidfAnalyzer
from ecomreview.schemas import Polarity, ReviewAnalysis


class TestB2TfidfAnalyzer:
    """Test suite for TF-IDF + Logistic Regression baseline."""

    def test_fit_save_and_predict(self, tmp_path):
        train_public = Path("data/public/train.jsonl")
        dev_gold = Path("data/gold/dev.jsonl")

        assert train_public.exists(), "public train.jsonl must exist"
        assert dev_gold.exists(), "gold dev.jsonl must exist"

        analyzer = B2TfidfAnalyzer(random_state=42)
        analyzer.fit(train_public, dev_gold)

        assert analyzer.is_fitted is True

        # Test inference on a positive raincoat review
        text_pos = "Áo mưa chất lượng rất tốt, mặc đi mưa to không bị thấm nước, rất hài lòng"
        pred_pos = analyzer.analyze_review(text_pos)

        assert isinstance(pred_pos, ReviewAnalysis)
        assert pred_pos.overall_sentiment == Polarity.POS
        assert len(pred_pos.opinions) >= 1

        # Test inference on a negative review
        text_neg = "Hàng kém chất lượng, áo rách tả tơi, giao hàng quá chậm"
        pred_neg = analyzer.analyze_review(text_neg)

        assert isinstance(pred_neg, ReviewAnalysis)
        assert pred_neg.overall_sentiment == Polarity.NEG

        # Test saving and loading pipeline
        save_path = tmp_path / "b2_pipeline.joblib"
        analyzer.save(save_path)
        assert save_path.exists()

        loaded = B2TfidfAnalyzer.load(save_path)
        assert loaded.is_fitted is True
        pred_loaded = loaded.analyze_review(text_pos)
        assert pred_loaded.overall_sentiment == pred_pos.overall_sentiment

        # Also save to canonical models/ path for downstream benchmark evaluation
        canonical_model_path = Path("models/b2_tfidf_pipeline.joblib")
        analyzer.save(canonical_model_path)
        assert canonical_model_path.exists()


# CreBy: MenBoyBMN
