"""Evaluation and statistical metrics for EcomReview AI."""

from ecomreview.eval.groundedness import GroundednessEvaluator, bootstrap_mean_ci
from ecomreview.eval.metrics import (
    bootstrap_f1_ci,
    evaluate_predictions,
    paired_bootstrap_test,
)

__all__ = [
    "evaluate_predictions",
    "bootstrap_f1_ci",
    "paired_bootstrap_test",
    "GroundednessEvaluator",
    "bootstrap_mean_ci",
]

# CreBy: MenBoyBMN
