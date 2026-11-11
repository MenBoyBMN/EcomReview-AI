"""Unit tests for Baseline 3 (B3): ViSoBERT / Subword Neural Analyzer."""

from ecomreview.analyze.b3_visobert import B3ViSoBERTAnalyzer
from ecomreview.schemas import Polarity, ReviewAnalysis


class TestB3ViSoBERTAnalyzer:
    """Test suite for B3 ViSoBERT analyzer on Track 1 and Track 2 (Cross-Domain)."""

    def test_fit_save_load_and_predict(self, tmp_path):
        b3 = B3ViSoBERTAnalyzer(enable_norm=True, random_state=42)
        b3.fit("data/public/train.jsonl")
        assert b3.is_fitted

        # Save and reload
        model_file = tmp_path / "b3_subword.joblib"
        b3.save(model_file)
        loaded = B3ViSoBERTAnalyzer.load(model_file)
        assert loaded.is_fitted

        # Track 1 prediction
        res_macro = loaded.analyze_review(
            "Máy chạy rất mượt, pin trâu, đáng tiền", is_macro_track=True
        )
        assert isinstance(res_macro, ReviewAnalysis)
        assert res_macro.overall_sentiment == Polarity.POS

        # Track 2 Cross-Domain prediction
        res_shop = loaded.analyze_review(
            "Áo mưa vải dày dặn nhưng đi mưa to bị thấm nước", is_macro_track=False
        )
        assert isinstance(res_shop, ReviewAnalysis)
        assert len(res_shop.opinions) >= 1

    def test_empty_input(self):
        b3 = B3ViSoBERTAnalyzer()
        b3.fit("data/public/train.jsonl")
        res = b3.analyze_review("   ")
        assert res.overall_sentiment == Polarity.NEU
        assert res.informative is False


# CreBy: MenBoyBMN
