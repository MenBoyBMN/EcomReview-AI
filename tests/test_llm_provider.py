"""Unit tests for Addon 11: UnifiedLLMClient (Gemini + Ollama), Self-Healing & YAML Lexicon."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ecomreview.llm_provider import EngineMode, UnifiedLLMClient, check_ollama_health
from ecomreview.normalize import load_social_lexicon, normalize_social_text
from ecomreview.schemas import Aspect, Polarity, ReviewAnalysis


class _DummyResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._payload


def test_ollama_self_healing_retry_succeeds_on_second_attempt() -> None:
    """Verify UnifiedLLMClient repairs invalid JSON on attempt 0 and succeeds on attempt 1."""
    calls: list[dict[str, Any]] = []

    def fake_post(url: str, json: dict[str, Any], timeout: int = 30) -> _DummyResponse:
        calls.append(json)
        if len(calls) == 1:
            # First attempt returns malformed JSON missing required fields
            return _DummyResponse({"message": {"content": '{"overall_sentiment": "INVALID_POL"}'}})
        # Second attempt returns valid ReviewAnalysis JSON after self-healing prompt
        valid_json = (
            '{"overall_sentiment": "negative", "informative": true, '
            '"opinions": [{"aspect": "WATERPROOF", "polarity": "negative", '
            '"evidence": "đi mưa bị thấm nước"}]}'
        )
        return _DummyResponse({"message": {"content": valid_json}})

    client = UnifiedLLMClient(
        mode=EngineMode.OLLAMA_LOCAL,
        ollama_model="qwen2.5:7b",
        max_self_heal_retries=2,
        http_post_fn=fake_post,
    )
    res = client.generate_structured(
        prompt="Áo đi mưa bị thấm nước",
        schema_cls=ReviewAnalysis,
    )

    assert len(calls) == 2
    assert res.overall_sentiment == Polarity.NEG
    assert res.opinions[0].aspect == Aspect.WATERPROOF


def test_ollama_offline_graceful_fallback_to_b1() -> None:
    """When local Ollama server is unreachable, UnifiedLLMClient falls back safely to B1."""

    def failing_post(url: str, json: dict[str, Any], timeout: int = 30) -> _DummyResponse:
        raise ConnectionError("Ollama local server not running")

    client = UnifiedLLMClient(
        mode=EngineMode.OLLAMA_LOCAL,
        http_post_fn=failing_post,
    )
    res = client.generate_structured(
        prompt="Áo mưa dày dặn chống thấm rất tốt",
        schema_cls=ReviewAnalysis,
        raw_review_for_fallback="Áo mưa dày dặn chống thấm rất tốt",
    )
    assert isinstance(res, ReviewAnalysis)
    assert res.overall_sentiment == Polarity.POS


def test_load_social_lexicon_yaml_and_health_check() -> None:
    """Verify YAML social lexicon loads new slang ('xịn' -> 'chất lượng tốt') & health check."""
    info = load_social_lexicon("knowledge/vn_social_lexicon.yaml")
    assert info["loaded"] is True
    assert info["teencode_count"] >= 48

    norm = normalize_social_text("Áo mưa xịn lắm nha sop", enable=True)
    assert "chất lượng tốt" in norm
    assert "shop" in norm

    health = check_ollama_health(base_url="http://127.0.0.1:59999", timeout_sec=0.2)
    assert health["online"] is False

    csv_path = Path("results/addon_local_vs_cloud.csv")
    assert csv_path.exists()
    with csv_path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert float(rows[1]["numeric_consistency_pct"]) == 100.0


# CreBy: MenBoyBMN
