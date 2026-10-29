"""Unit tests for evaluation metrics and bootstrap statistical tests."""

import pytest

from ecomreview.eval.metrics import (
    bootstrap_f1_ci,
    evaluate_predictions,
    paired_bootstrap_test,
)
from ecomreview.schemas import Aspect, AspectOpinion, Polarity, ReviewAnalysis


class TestBootstrapMetrics:
    """Tests for bootstrap confidence intervals and paired significance tests."""

    def test_bootstrap_perfect_agreement(self):
        y_true = ["positive", "negative", "neutral", "positive"] * 10
        y_pred = list(y_true)

        pt, low, high = bootstrap_f1_ci(y_true, y_pred, n_boot=200, seed=42)
        assert pt == 1.0
        assert low == 1.0
        assert high == 1.0

    def test_bootstrap_imperfect_agreement(self):
        y_true = ["positive", "negative", "neutral", "positive"] * 10
        y_pred = ["positive", "negative", "positive", "positive"] * 10

        pt, low, high = bootstrap_f1_ci(y_true, y_pred, n_boot=200, seed=42)
        assert 0.0 < pt < 1.0
        assert low <= pt <= high

    def test_paired_bootstrap_significant_difference(self):
        y_true = ["positive"] * 30 + ["negative"] * 30
        y_pred_a = ["positive"] * 30 + ["negative"] * 30  # Perfect model A
        y_pred_b = ["negative"] * 30 + ["positive"] * 30  # Worst model B

        delta, p_val, ci_l, ci_h = paired_bootstrap_test(
            y_true, y_pred_a, y_pred_b, n_boot=200, seed=42
        )
        assert delta > 0.9
        assert p_val < 0.01
        assert ci_l > 0.8


class TestEvaluatePredictions:
    """Tests for end-to-end evaluate_predictions function."""

    def test_perfect_prediction_review_analysis_objects(self):
        gold = [
            ReviewAnalysis(
                overall_sentiment=Polarity.POS,
                opinions=[
                    AspectOpinion(
                        aspect=Aspect.WATERPROOF,
                        polarity=Polarity.POS,
                        evidence="chống nước tốt",
                    )
                ],
                informative=True,
            ),
            ReviewAnalysis(
                overall_sentiment=Polarity.NEG,
                opinions=[
                    AspectOpinion(
                        aspect=Aspect.MATERIAL_DURABILITY,
                        polarity=Polarity.NEG,
                        evidence="vải mỏng dễ rách",
                    )
                ],
                informative=True,
            ),
        ]
        pred = [
            ReviewAnalysis(
                overall_sentiment=Polarity.POS,
                opinions=[
                    AspectOpinion(
                        aspect=Aspect.WATERPROOF,
                        polarity=Polarity.POS,
                        evidence="chống nước tốt",
                    )
                ],
                informative=True,
            ),
            ReviewAnalysis(
                overall_sentiment=Polarity.NEG,
                opinions=[
                    AspectOpinion(
                        aspect=Aspect.MATERIAL_DURABILITY,
                        polarity=Polarity.NEG,
                        evidence="vải mỏng dễ rách",
                    )
                ],
                informative=True,
            ),
        ]
        texts = [
            "Áo mưa chống nước tốt lắm",
            "Vải mỏng dễ rách quá",
        ]

        metrics = evaluate_predictions(gold, pred, texts=texts, n_boot=100)
        assert metrics["overall_sentiment_f1"] == 1.0
        assert metrics["aspect_detection_f1"] == 1.0
        assert metrics["absa_macro_f1"] == 1.0
        assert metrics["quote_fidelity"] == 1.0

    def test_quote_fidelity_detection(self):
        gold = [
            {"overall_sentiment": "positive", "opinions": []},
            {"overall_sentiment": "negative", "opinions": []},
        ]
        pred = [
            {
                "overall_sentiment": "positive",
                "opinions": [
                    {
                        "aspect": "WATERPROOF",
                        "polarity": "positive",
                        "evidence": "chống thấm",  # in text
                    }
                ],
            },
            {
                "overall_sentiment": "negative",
                "opinions": [
                    {
                        "aspect": "PRICE_VALUE",
                        "polarity": "negative",
                        "evidence": "đắt đỏ vô lý",  # NOT in text
                    }
                ],
            },
        ]
        texts = [
            "Áo chống thấm rất ổn nha mn",
            "Màu áo xấu quá",
        ]

        metrics = evaluate_predictions(gold, pred, texts=texts, n_boot=100)
        assert metrics["quote_fidelity"] == 0.5  # 1 out of 2 valid

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="Length mismatch"):
            evaluate_predictions([{"overall_sentiment": "positive"}], [])


# CreBy: MenBoyBMN
