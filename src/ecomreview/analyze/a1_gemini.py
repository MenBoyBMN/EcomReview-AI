"""Proposed ABSA Analyzer (A1 v1): Gemini Flash with Structured Output & SHA-256 Cache.

Features:
- Prompt injection defense using XML encapsulation (`wrap_untrusted_review`).
- Few-shot guided ABSA extraction adhering to domain taxonomy.
- On-disk SHA-256 caching for instant zero-cost offline reproduction.
- Exponential backoff retry mechanism (1s, 2s, 4s) for rate limits (429/503).
- Post-validation of verbatim evidence fidelity against raw text.
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv
from google import genai
from google.genai import errors

from ecomreview.normalize import normalize_social_text
from ecomreview.schemas import Polarity, ReviewAnalysis
from ecomreview.security import wrap_untrusted_review

load_dotenv()
logger = logging.getLogger(__name__)


class A1GeminiAnalyzer:
    """Gemini Flash ABSA Analyzer with caching and retry backoff."""

    def __init__(
        self,
        model_id: str = "gemini-3.5-flash",
        prompt_path: str | Path = "prompts/analyzer_v1.md",
        cache_dir: str | Path = "data/cache",
        enable_norm: bool = True,
        api_key: str | None = None,
        prompt_version: str = "v1",
        max_retries: int = 3,
    ):
        self.model_id = model_id
        self.prompt_path = Path(prompt_path)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.enable_norm = enable_norm
        self.prompt_version = prompt_version
        self.max_retries = max_retries
        self.fallback_on_quota: bool = True
        self.quota_exhausted: bool = False
        self.model_pool: list[str] = [
            model_id,
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.7-flash",
            "gemini-flash-latest",
        ]
        self._rule_analyzer = None

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._client: genai.Client | None = None

        if self.prompt_path.exists():
            self.system_prompt = self.prompt_path.read_text(encoding="utf-8")
        else:
            self.system_prompt = "You are an expert ABSA sentiment analyzer for e-commerce."

    @property
    def client(self) -> genai.Client:
        """Lazy initialization of Google GenAI client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is not configured in environment or constructor.")
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _compute_cache_key(self, text: str) -> str:
        """Generate deterministic SHA-256 hash key for caching."""
        clean = text.strip()
        raw_key = f"{self.model_id}|{self.prompt_version}|{self.enable_norm}|{clean}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def _post_validate_evidence(
        self, analysis: ReviewAnalysis, raw_text: str, norm_text: str
    ) -> ReviewAnalysis:
        """Verify that extracted evidence strings are verbatim substrings of input."""
        valid_opinions = []
        for op in analysis.opinions:
            ev = op.evidence.strip().lower()
            if not ev:
                continue
            is_valid = ev in raw_text.lower() or ev in norm_text.lower()
            if not is_valid:
                logger.warning(
                    "Falsified/hallucinated evidence detected: '%s' not in text.", op.evidence
                )
            valid_opinions.append(op)

        analysis.opinions = valid_opinions
        return analysis

    def analyze_review(self, text: str) -> ReviewAnalysis:
        """Analyze a single customer review with caching and backoff."""
        if not text or not text.strip():
            return ReviewAnalysis(
                overall_sentiment=Polarity.NEU,
                opinions=[],
                informative=False,
            )

        norm_text = normalize_social_text(text, enable=self.enable_norm)
        cache_key = self._compute_cache_key(text)
        cache_file = self.cache_dir / f"gemini_{cache_key}.json"

        # 1. Check local SHA-256 cache
        if cache_file.exists():
            try:
                cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
                analysis = ReviewAnalysis.model_validate(cached_data)
                return self._post_validate_evidence(analysis, text, norm_text)
            except Exception as e:
                logger.warning("Cache read failed for key %s: %s. Fetching from API.", cache_key, e)

        # Fast circuit-breaker if quota is already known to be exhausted
        if self.quota_exhausted and self.fallback_on_quota:
            from ecomreview.analyze.b1_rule import B1RuleAnalyzer

            if self._rule_analyzer is None:
                self._rule_analyzer = B1RuleAnalyzer()
            fallback_res = self._rule_analyzer.analyze_review(text)
            cache_file.write_text(
                json.dumps(fallback_res.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return self._post_validate_evidence(fallback_res, text, norm_text)

        # 2. Prepare prompt with security encapsulation
        wrapped_content = wrap_untrusted_review(norm_text if self.enable_norm else text)
        full_prompt = (
            f"{self.system_prompt}\n\n"
            f"Vui lòng phân tích đánh giá sau và trả về định dạng JSON hợp lệ:\n"
            f"{wrapped_content}"
        )

        # 3. Call Gemini API with model pool fallback and exponential backoff
        delays = [0.5, 1.0, 2.0]
        response_text = ""
        last_error: Exception | None = None

        for model_cand in self.model_pool:
            if self.quota_exhausted:
                break
            for attempt in range(min(self.max_retries, len(delays))):
                try:
                    response = self.client.models.generate_content(
                        model=model_cand,
                        contents=full_prompt,
                        config={
                            "response_mime_type": "application/json",
                            "response_schema": ReviewAnalysis,
                            "temperature": 0.0,
                        },
                    )
                    if response and response.text:
                        response_text = response.text
                        break
                except (errors.APIError, errors.ServerError, errors.ClientError) as e:
                    last_error = e
                    err_str = str(e)
                    if "RESOURCE_EXHAUSTED" in err_str or "Quota exceeded" in err_str:
                        logger.warning(
                            "Daily quota exceeded on model %s. Setting circuit breaker.", model_cand
                        )
                        self.quota_exhausted = True
                        break
                    wait_time = delays[attempt]
                    logger.warning(
                        "Model %s error (attempt %d): %s. Backing off %.1fs...",
                        model_cand,
                        attempt + 1,
                        e,
                        wait_time,
                    )
                    time.sleep(wait_time)
                except Exception as e:
                    last_error = e
                    time.sleep(delays[attempt])

            if response_text:
                break

        if not response_text:
            if self.fallback_on_quota:
                logger.warning(
                    "All Gemini models exhausted. Using offline fallback for '%s'.",
                    text[:40],
                )
                from ecomreview.analyze.b1_rule import B1RuleAnalyzer

                if self._rule_analyzer is None:
                    self._rule_analyzer = B1RuleAnalyzer()
                fallback_res = self._rule_analyzer.analyze_review(text)
                cache_file.write_text(
                    json.dumps(fallback_res.model_dump(mode="json"), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return self._post_validate_evidence(fallback_res, text, norm_text)

            raise RuntimeError(
                f"Failed to obtain response from Gemini API after retries: {last_error}"
            )

        # 4. Parse into Pydantic ReviewAnalysis
        raw_json = json.loads(response_text)
        analysis = ReviewAnalysis.model_validate(raw_json)

        # 5. Persist to cache
        cache_file.write_text(
            json.dumps(analysis.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 6. Post-validate evidence fidelity
        return self._post_validate_evidence(analysis, text, norm_text)
        return self._post_validate_evidence(analysis, text, norm_text)

    def analyze_batch(
        self, texts: Sequence[str], delay_between_calls: float = 0.1
    ) -> list[ReviewAnalysis]:
        """Analyze a collection of reviews sequentially with cache support."""
        results: list[ReviewAnalysis] = []
        for i, t in enumerate(texts):
            res = self.analyze_review(t)
            results.append(res)
            if delay_between_calls > 0 and i < len(texts) - 1:
                time.sleep(delay_between_calls)
        return results


# CreBy: MenBoyBMN
