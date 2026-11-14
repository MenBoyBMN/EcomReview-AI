"""Factory module providing dynamic instantiation and caching of ABSA analyzers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from ecomreview.analyze.a1_gemini import A1GeminiAnalyzer, post_validate_evidence
from ecomreview.analyze.b1_rule import B1RuleAnalyzer
from ecomreview.llm_provider import EngineMode, UnifiedLLMClient
from ecomreview.normalize import normalize_social_text
from ecomreview.schemas import Polarity, ReviewAnalysis
from ecomreview.security import wrap_untrusted_review

SUPPORTED_METHODS: tuple[str, ...] = ("b1_rule", "a1_gemini_v2", "a1_ollama")
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PROMPT_PATH = _PROJECT_ROOT / "prompts" / "analyzer_v2_frozen.md"


class OllamaABSAAnalyzer:
    """Local Ollama ABSA analyzer adapter routed through UnifiedLLMClient with B1 fallback."""

    def __init__(
        self,
        prompt_path: str | Path = _DEFAULT_PROMPT_PATH,
        enable_norm: bool = True,
        llm_client: UnifiedLLMClient | None = None,
    ):
        p = Path(prompt_path)
        self.prompt_path = p if p.is_absolute() else _PROJECT_ROOT / p
        self.enable_norm = enable_norm
        self.client = llm_client or UnifiedLLMClient(mode=EngineMode.OLLAMA_LOCAL)
        self.last_used_fallback: bool = False
        if self.prompt_path.exists():
            self.system_prompt = self.prompt_path.read_text(encoding="utf-8")
        else:
            self.system_prompt = "You are an expert ABSA sentiment analyzer for e-commerce."

    def analyze_review(self, text: str) -> ReviewAnalysis:
        """Analyze a single customer review via local Ollama or fallback cleanly to B1Rule."""
        self.last_used_fallback = False
        if not text or not text.strip():
            return ReviewAnalysis(overall_sentiment=Polarity.NEU, opinions=[], informative=False)

        norm_text = normalize_social_text(text, enable=self.enable_norm)
        wrapped = wrap_untrusted_review(norm_text if self.enable_norm else text)
        prompt = f"Vui lòng phân tích đánh giá sau và trả về JSON hợp lệ:\n{wrapped}"
        res = self.client.generate_structured(
            prompt=prompt,
            schema_cls=ReviewAnalysis,
            system_instruction=self.system_prompt,
            raw_review_for_fallback=text,
        )
        self.last_used_fallback = self.client.last_used_fallback
        return post_validate_evidence(res, text, norm_text)


@lru_cache(maxsize=4)
def get_analyzer(method: str = "a1_gemini_v2") -> Any:
    """Instantiate and return cached analyzer according to method name.

    Args:
        method: One of ('b1_rule', 'a1_gemini_v2', 'a1_ollama').

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
            prompt_path=_DEFAULT_PROMPT_PATH,
            prompt_version="v2",
            enable_norm=True,
        )

    if m in ("a1_ollama", "ollama", "ollama_qwen"):
        return OllamaABSAAnalyzer(
            prompt_path=_DEFAULT_PROMPT_PATH,
            enable_norm=True,
        )

    raise ValueError(f"Unsupported analyzer_method '{method}'. Choose from {SUPPORTED_METHODS}")


# CreBy: MenBoyBMN
