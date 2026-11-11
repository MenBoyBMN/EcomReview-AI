"""Factory module providing dynamic instantiation and caching of ABSA analyzers."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from ecomreview.analyze.a1_gemini import A1GeminiAnalyzer
from ecomreview.analyze.b1_rule import B1RuleAnalyzer

SUPPORTED_METHODS: tuple[str, ...] = ("b1_rule", "a1_gemini_v2")


@lru_cache(maxsize=4)
def get_analyzer(method: str = "a1_gemini_v2") -> Any:
    """Instantiate and return cached analyzer according to method name.

    Args:
        method: One of ('b1_rule', 'a1_gemini_v2').

    Returns:
        Analyzer instance with analyze_review(text: str) -> ReviewAnalysis interface.

    Raises:
        ValueError: If method is not supported.
    """
    m = method.strip().lower()
    if m == "b1_rule":
        return B1RuleAnalyzer(enable_norm=True)

    if m in ("a1_gemini_v2", "gemini_v2", "gemini"):
        return A1GeminiAnalyzer(
            prompt_path="prompts/analyzer_v2_frozen.md",
            prompt_version="v2",
            enable_norm=True,
        )

    raise ValueError(f"Unsupported analyzer_method '{method}'. Choose from {SUPPORTED_METHODS}")


# CreBy: MenBoyBMN
