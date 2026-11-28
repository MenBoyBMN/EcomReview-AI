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
import threading
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import errors

from ecomreview.analyze.cache_store import ABSAAnalysisCache
from ecomreview.llm_provider import DEFAULT_GEMINI_MODEL, resolve_gemini_pool
from ecomreview.normalize import normalize_social_text
from ecomreview.schemas import Polarity, ReviewAnalysis
from ecomreview.security import wrap_untrusted_review

load_dotenv()
logger = logging.getLogger(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _resolve_repo_path(path_val: str | Path) -> Path:
    p = Path(path_val)
    return p if p.is_absolute() else _PROJECT_ROOT / p


def post_validate_evidence(
    analysis: ReviewAnalysis, raw_text: str, norm_text: str
) -> ReviewAnalysis:
    """Verify that extracted evidence strings are verbatim substrings of input."""
    valid_opinions = []
    raw_lower = raw_text.lower()
    norm_lower = norm_text.lower()
    for op in analysis.opinions:
        ev = op.evidence.strip().lower()
        if not ev:
            continue
        is_valid = ev in raw_lower or ev in norm_lower
        if not is_valid:
            logger.warning(
                "Falsified/hallucinated evidence detected: '%s' not in text.", op.evidence
            )
            op.evidence_ok = False
        else:
            op.evidence_ok = True
        valid_opinions.append(op)

    analysis.opinions = valid_opinions
    return analysis


class A1GeminiAnalyzer:
    """Gemini Flash ABSA Analyzer with caching and retry backoff."""

    def __init__(
        self,
        model_id: str = DEFAULT_GEMINI_MODEL,
        prompt_path: str | Path = "prompts/analyzer_v2_frozen.md",
        cache_dir: str | Path = "data/cache",
        enable_norm: bool = True,
        api_key: str | None = None,
        prompt_version: str = "v2",
        max_retries: int = 3,
        quota_cooldown_sec: float = 120.0,
        redis_client: Any = None,
    ):
        effective_model, self.model_pool = resolve_gemini_pool(model_id)
        self.model_id = effective_model
        self.prompt_path = _resolve_repo_path(prompt_path)
        self.cache_dir = _resolve_repo_path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_store = ABSAAnalysisCache(cache_dir=self.cache_dir, redis_client=redis_client)
        self.enable_norm = enable_norm
        self.prompt_version = prompt_version
        self.max_retries = max_retries
        self.quota_cooldown_sec = quota_cooldown_sec
        self.fallback_on_quota: bool = True
        self._state_lock = threading.Lock()
        self._tls = threading.local()
        self._quota_exhausted_until: float = 0.0
        self._exhausted_models: set[str] = set()
        self._model_cooldown_until: dict[str, float] = {}
        self._call_counter: int = 0
        self._rule_analyzer = None

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._client: genai.Client | None = None

        if self.prompt_path.exists():
            self.system_prompt = self.prompt_path.read_text(encoding="utf-8")
        else:
            self.system_prompt = "You are an expert ABSA sentiment analyzer for e-commerce."

    @property
    def last_used_fallback(self) -> bool:
        """Thread-local flag indicating whether the current thread fell back to B1."""
        return bool(getattr(self._tls, "last_used_fallback", False))

    @last_used_fallback.setter
    def last_used_fallback(self, value: bool) -> None:
        self._tls.last_used_fallback = bool(value)

    @property
    def quota_exhausted(self) -> bool:
        """Return True while the global quota circuit-breaker cooldown is active."""
        with self._state_lock:
            return time.monotonic() < self._quota_exhausted_until

    @quota_exhausted.setter
    def quota_exhausted(self, value: bool) -> None:
        with self._state_lock:
            self._quota_exhausted_until = (
                time.monotonic() + self.quota_cooldown_sec if value else 0.0
            )

    @property
    def client(self) -> genai.Client:
        """Lazy thread-safe initialization of Google GenAI client."""
        with self._state_lock:
            if self._client is None:
                if not self.api_key:
                    raise ValueError(
                        "GEMINI_API_KEY is not configured in environment or constructor."
                    )
                self._client = genai.Client(api_key=self.api_key, http_options={"timeout": 15000})
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
        return post_validate_evidence(analysis, raw_text, norm_text)

    def _fallback_b1(self, text: str, norm_text: str) -> ReviewAnalysis:
        """Run deterministic B1 rule fallback respecting `self.enable_norm`."""
        from ecomreview.analyze.b1_rule import B1RuleAnalyzer

        self.last_used_fallback = True
        with self._state_lock:
            if self._rule_analyzer is None:
                self._rule_analyzer = B1RuleAnalyzer(enable_norm=self.enable_norm)
            rule_analyzer = self._rule_analyzer
        fallback_res = rule_analyzer.analyze_review(text)
        return self._post_validate_evidence(fallback_res, text, norm_text)

    def analyze_review(self, text: str) -> ReviewAnalysis:
        """Analyze a single customer review with caching and backoff."""
        self.last_used_fallback = False
        if not text or not text.strip():
            return ReviewAnalysis(
                overall_sentiment=Polarity.NEU,
                opinions=[],
                informative=False,
            )

        norm_text = normalize_social_text(text, enable=self.enable_norm)
        cache_key = self._compute_cache_key(text)

        # 1. Check shared Redis + local SHA-256 cache
        candidate_keys = [cache_key]
        clean = text.strip()
        if norm_text.strip() == clean:
            alt_k1 = hashlib.sha256(
                f"{self.model_id}|{self.prompt_version}|True|{clean}".encode("utf-8")
            ).hexdigest()
            alt_k2 = hashlib.sha256(f"{self.model_id}|v1|True|{clean}".encode("utf-8")).hexdigest()
            candidate_keys.extend([alt_k1, alt_k2])
        elif self.enable_norm:
            alt_v1 = hashlib.sha256(f"{self.model_id}|v1|True|{clean}".encode("utf-8")).hexdigest()
            candidate_keys.append(alt_v1)

        for ck in dict.fromkeys(candidate_keys):
            cached_data = self.cache_store.get(ck)
            if cached_data is not None:
                try:
                    analysis = ReviewAnalysis.model_validate(cached_data)
                    if ck != cache_key:
                        self.cache_store.set(cache_key, analysis.model_dump(mode="json"))
                    return self._post_validate_evidence(analysis, text, norm_text)
                except Exception as e:
                    logger.warning("Cache validation failed for key %s: %s.", ck, e)

        # Fast circuit-breaker if ALL models in pool are in cooldown or API key is not configured
        if (self.quota_exhausted or not self.api_key) and self.fallback_on_quota:
            if not self.api_key:
                self.quota_exhausted = True
            return self._fallback_b1(text, norm_text)

        # 2. Prepare prompt with security encapsulation
        wrapped_content = wrap_untrusted_review(norm_text if self.enable_norm else text)
        full_prompt = (
            f"{self.system_prompt}\n\n"
            f"Vui lòng phân tích đánh giá sau và trả về định dạng JSON hợp lệ:\n"
            f"{wrapped_content}"
        )

        # 3. Call Gemini API with round-robin model rotation and bounded backoff
        delays = [1.0, 2.0, 4.0]
        response_text = ""
        last_error: Exception | None = None
        now_mono = time.monotonic()

        with self._state_lock:
            active_pool = [
                m
                for m in self.model_pool
                if m not in self._exhausted_models
                and self._model_cooldown_until.get(m, 0.0) <= now_mono
            ]
            if not active_pool:
                active_pool = [m for m in self.model_pool if m not in self._exhausted_models]
            if not active_pool:
                active_pool = list(self.model_pool)

            start_idx = self._call_counter % len(active_pool)
            self._call_counter += 1
        rotated_pool = active_pool[start_idx:] + active_pool[:start_idx]

        for model_cand in rotated_pool:
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
                    if "404" in err_str or "NOT_FOUND" in err_str:
                        with self._state_lock:
                            self._exhausted_models.add(model_cand)
                        break
                    if (
                        "RESOURCE_EXHAUSTED" in err_str
                        or "Quota exceeded" in err_str
                        or "429" in err_str
                    ):
                        logger.warning(
                            "Rate/quota limit on model %s. Cooling down 60s and switching model...",
                            model_cand,
                        )
                        with self._state_lock:
                            self._model_cooldown_until[model_cand] = time.monotonic() + 60.0
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
            self.quota_exhausted = True
            if self.fallback_on_quota:
                logger.warning(
                    "All Gemini models in pool failed/exhausted. Using offline fallback for '%s'.",
                    text[:40],
                )
                return self._fallback_b1(text, norm_text)

            raise RuntimeError(
                f"Failed to obtain response from Gemini API after retries: {last_error}"
            )

        # 4. Parse into Pydantic ReviewAnalysis with fallback guard
        try:
            raw_json = json.loads(response_text)
            analysis = ReviewAnalysis.model_validate(raw_json)
        except Exception as exc:
            if self.fallback_on_quota:
                logger.warning("Failed to parse Gemini JSON output (%s). Falling back to B1.", exc)
                return self._fallback_b1(text, norm_text)
            raise RuntimeError(f"Invalid Gemini JSON response: {exc}") from exc

        # 5. Persist genuine Gemini response to shared Redis + disk cache
        self.cache_store.set(cache_key, analysis.model_dump(mode="json"))

        # 6. Post-validate evidence fidelity
        return self._post_validate_evidence(analysis, text, norm_text)


# CreBy: MenBoyBMN
