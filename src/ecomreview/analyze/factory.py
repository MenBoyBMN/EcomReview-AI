"""Factory module providing dynamic instantiation and caching of ABSA analyzers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from ecomreview.analyze.a1_gemini import A1GeminiAnalyzer
from ecomreview.analyze.b1_rule import B1RuleAnalyzer
from ecomreview.analyze.b2_tfidf import B2TfidfAnalyzer
from ecomreview.analyze.b3_visobert import B3ViSoBERTAnalyzer

SUPPORTED_METHODS: tuple[str, ...] = ("b1_rule", "b2_tfidf", "b3_visobert", "a1_gemini_v2")


@lru_cache(maxsize=4)
def get_analyzer(method: str = "a1_gemini_v2") -> Any:
    """Instantiate and return cached analyzer according to method name.

    Args:
        method: One of ('b1_rule', 'b2_tfidf', 'b3_visobert', 'a1_gemini_v2').

    Returns:
        Analyzer instance with analyze_review(text: str) -> ReviewAnalysis interface.

    Raises:
        ValueError: If method is not supported.
        FileNotFoundError: If model checkpoint required for B2/B3 does not exist.
    """
    m = method.strip().lower()
    if m == "b1_rule":
        return B1RuleAnalyzer(enable_norm=True)

    if m == "b2_tfidf":
        model_path = Path("models/b2_tfidf_pipeline.joblib")
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model checkpoint for B2 TF-IDF not found at {model_path}. Run training first."
            )
        return B2TfidfAnalyzer.load(model_path)

    if m == "b3_visobert":
        model_path = Path("models/visobert/b3_subword_model.joblib")
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model checkpoint for B3 ViSoBERT not found at {model_path}. Run training first."
            )
        return B3ViSoBERTAnalyzer.load(model_path)

    if m in ("a1_gemini_v2", "gemini_v2", "gemini"):
        return A1GeminiAnalyzer(
            prompt_path="prompts/analyzer_v2_frozen.md",
            prompt_version="v2",
            enable_norm=True,
        )

    raise ValueError(f"Unsupported analyzer_method '{method}'. Choose from {SUPPORTED_METHODS}")


# CreBy: MenBoyBMN
