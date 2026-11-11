"""Unified LLM Provider Layer supporting Cloud Gemini Flash and Local Ollama (Addon 11).

Provides a plug-and-play abstraction (`UnifiedLLMClient`) with:
- `EngineMode.GEMINI_CLOUD`: Google GenAI SDK (`gemini-3.5-flash`) with Structured Output.
- `EngineMode.OLLAMA_LOCAL`: Local Ollama (`qwen2.5:7b` via `/api/chat` with native JSON Schema).
- Self-Healing JSON Retry: Up to 2 automatic schema-repair retries when local 7B output drifts.
- Deterministic Offline Fallback (`B1RuleAnalyzer`) if Cloud API key or Local Ollama is offline.
"""

from __future__ import annotations

import json
import os
from enum import Enum
from typing import Any, Callable, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from ecomreview.analyze.b1_rule import B1RuleAnalyzer
from ecomreview.schemas import ReviewAnalysis

T = TypeVar("T", bound=BaseModel)


class EngineMode(str, Enum):
    """Supported AI Backend Engines for EcomReview AI."""

    GEMINI_CLOUD = "gemini"
    OLLAMA_LOCAL = "ollama"


def check_ollama_health(
    base_url: str | None = None,
    timeout_sec: float = 1.5,
) -> dict[str, Any]:
    """Check whether local Ollama service is reachable and list available models."""
    url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
    try:
        resp = requests.get(f"{url}/api/tags", timeout=timeout_sec)
        if resp.status_code == 200:
            data = resp.json() or {}
            models = [str(m.get("name", "")) for m in data.get("models", [])]
            return {"online": True, "base_url": url, "models": models}
    except Exception:
        pass
    return {"online": False, "base_url": url, "models": []}


class UnifiedLLMClient:
    """Unified structured-output LLM client with Self-Healing Retry for Cloud & Local AI."""

    def __init__(
        self,
        mode: EngineMode | str = EngineMode.GEMINI_CLOUD,
        gemini_model: str = "gemini-3.5-flash",
        ollama_model: str = "qwen2.5:7b",
        ollama_base_url: str | None = None,
        api_key: str | None = None,
        max_self_heal_retries: int = 2,
        http_post_fn: Callable[..., Any] | None = None,
    ):
        self.mode = mode if isinstance(mode, EngineMode) else EngineMode(str(mode).lower())
        self.gemini_model = gemini_model
        self.ollama_model = os.getenv("OLLAMA_MODEL", ollama_model)
        self.ollama_base_url = (
            ollama_base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ).rstrip("/")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.max_self_heal_retries = max_self_heal_retries
        self._http_post = http_post_fn or requests.post
        self._b1_fallback = B1RuleAnalyzer(enable_norm=True)

    def generate_structured(
        self,
        prompt: str,
        schema_cls: type[T],
        system_instruction: str = "",
        raw_review_for_fallback: str = "",
    ) -> T:
        """Generate a validated Pydantic object from either Gemini Cloud or Ollama Local."""
        if self.mode == EngineMode.OLLAMA_LOCAL:
            return self._call_ollama_with_self_healing(
                prompt=prompt,
                schema_cls=schema_cls,
                system_instruction=system_instruction,
                raw_review_for_fallback=raw_review_for_fallback,
            )
        return self._call_gemini_or_fallback(
            prompt=prompt,
            schema_cls=schema_cls,
            system_instruction=system_instruction,
            raw_review_for_fallback=raw_review_for_fallback,
        )

    def _call_ollama_with_self_healing(
        self,
        prompt: str,
        schema_cls: type[T],
        system_instruction: str = "",
        raw_review_for_fallback: str = "",
    ) -> T:
        """Call local Ollama `/api/chat` with JSON schema enforcement and self-healing retry."""
        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        json_schema = schema_cls.model_json_schema()
        last_error = ""

        for attempt in range(self.max_self_heal_retries + 1):
            if attempt > 0 and last_error:
                heal_msg = (
                    f"JSON trước đó của bạn bị lỗi cấu trúc Pydantic: {last_error}. "
                    f"Hãy sửa lại và chỉ trả về JSON hợp lệ khớp chính xác với schema."
                )
                messages.append({"role": "user", "content": heal_msg})

            payload = {
                "model": self.ollama_model,
                "messages": messages,
                "format": json_schema,
                "options": {"temperature": 0.0, "seed": 42},
                "stream": False,
            }
            try:
                resp = self._http_post(
                    f"{self.ollama_base_url}/api/chat",
                    json=payload,
                    timeout=30,
                )
                resp.raise_for_status()
                body = resp.json()
                raw_content = str(body.get("message", {}).get("content", "")).strip()
                return schema_cls.model_validate_json(raw_content)
            except ValidationError as ve:
                last_error = str(ve.errors()[0].get("msg", str(ve)))
                continue
            except json.JSONDecodeError as je:
                last_error = f"Invalid JSON syntax: {je}"
                continue
            except Exception as exc:
                last_error = str(exc)
                break

        if schema_cls is ReviewAnalysis and raw_review_for_fallback:
            return self._b1_fallback.analyze_review(raw_review_for_fallback)  # type: ignore[return-value]
        raise RuntimeError(f"Ollama structured generation failed after retries: {last_error}")

    def _call_gemini_or_fallback(
        self,
        prompt: str,
        schema_cls: type[T],
        system_instruction: str = "",
        raw_review_for_fallback: str = "",
    ) -> T:
        """Call Google Gemini Flash with Structured Output or fallback safely when offline."""
        if self.api_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.api_key, http_options={"timeout": 15000})
                full_prompt = f"{system_instruction}\n\n{prompt}".strip()
                response = client.models.generate_content(
                    model=self.gemini_model,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema_cls,
                        temperature=0.0,
                        seed=42,
                    ),
                )
                if response.text:
                    return schema_cls.model_validate_json(response.text)
            except Exception:
                pass

        if schema_cls is ReviewAnalysis and raw_review_for_fallback:
            return self._b1_fallback.analyze_review(raw_review_for_fallback)  # type: ignore[return-value]
        raise RuntimeError("Gemini Cloud API unavailable and no fallback review provided.")


# CreBy: MenBoyBMN
