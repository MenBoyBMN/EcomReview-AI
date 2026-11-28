"""Production Prometheus exposition metrics and optional Sentry error tracking."""

from __future__ import annotations

import logging
import os
import re
import threading
from collections import defaultdict
from typing import Any

from ecomreview.security import scrub_pii

logger = logging.getLogger(__name__)

_PATH_NUM_RE = re.compile(r"/\d+(?=/|$)")
_PATH_REV_ID_RE = re.compile(r"(/api/v1/reviews/)([^/]+)(/repl(?:y-draft|ies))")
_PATH_SHOP_RE = re.compile(r"(/api/v1/shops/)([^/]+)(/.*|$)")


def normalize_metric_path(path: str) -> str:
    """Collapse dynamic IDs/slugs in URL paths to keep Prometheus cardinality bounded."""
    norm = _PATH_NUM_RE.sub("/{id}", path or "/")
    norm = _PATH_REV_ID_RE.sub(r"\1{review_id}\3", norm)
    norm = _PATH_SHOP_RE.sub(r"\1{slug}\3", norm)
    return norm


class MetricsRegistry:
    """Thread-safe in-process Prometheus metrics collector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._http_counts: dict[tuple[str, str, str], int] = defaultdict(int)
        self._http_duration_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._http_duration_count: dict[tuple[str, str], int] = defaultdict(int)
        self._cache_events: dict[str, int] = defaultdict(int)
        self._llm_fallbacks: dict[str, int] = defaultdict(int)

    def observe_http(self, method: str, path: str, status_code: int, duration_sec: float) -> None:
        """Record an HTTP request count and duration."""
        norm_path = normalize_metric_path(path)
        clean_method = (method or "GET").upper()
        with self._lock:
            self._http_counts[(clean_method, norm_path, str(status_code))] += 1
            self._http_duration_sum[(clean_method, norm_path)] += max(0.0, float(duration_sec))
            self._http_duration_count[(clean_method, norm_path)] += 1

    def inc_cache_event(self, tier: str) -> None:
        """Increment ABSA cache counter ('redis_hit', 'disk_hit', or 'miss')."""
        with self._lock:
            self._cache_events[tier] += 1

    def inc_llm_fallback(self, scenario_tag: str = "global") -> None:
        """Increment deterministic B1 rule fallback counter."""
        with self._lock:
            self._llm_fallbacks[scenario_tag or "global"] += 1

    def render_prometheus(self, redis_client: Any = None) -> str:
        """Render all collected metrics in Prometheus text exposition format 0.0.4."""
        lines: list[str] = [
            "# HELP ecomreview_http_requests_total Total HTTP requests handled.",
            "# TYPE ecomreview_http_requests_total counter",
        ]
        with self._lock:
            http_counts = dict(self._http_counts)
            dur_sum = dict(self._http_duration_sum)
            dur_cnt = dict(self._http_duration_count)
            cache_ev = dict(self._cache_events)
            fallbacks = dict(self._llm_fallbacks)

        for (method, path, code), val in sorted(http_counts.items()):
            lines.append(
                f"ecomreview_http_requests_total"
                f'{{method="{method}",path="{path}",status="{code}"}} {val}'
            )

        lines.extend(
            [
                "# HELP ecomreview_http_request_duration_seconds_sum "
                "Total HTTP request duration in seconds.",
                "# TYPE ecomreview_http_request_duration_seconds_sum counter",
            ]
        )
        for (method, path), val in sorted(dur_sum.items()):
            lines.append(
                f"ecomreview_http_request_duration_seconds_sum"
                f'{{method="{method}",path="{path}"}} {val:.6f}'
            )

        lines.extend(
            [
                "# HELP ecomreview_http_request_duration_seconds_count Total timed HTTP requests.",
                "# TYPE ecomreview_http_request_duration_seconds_count counter",
            ]
        )
        for (method, path), val in sorted(dur_cnt.items()):
            lines.append(
                f"ecomreview_http_request_duration_seconds_count"
                f'{{method="{method}",path="{path}"}} {val}'
            )

        lines.extend(
            [
                "# HELP ecomreview_absa_cache_events_total ABSA analysis cache hit/miss counters.",
                "# TYPE ecomreview_absa_cache_events_total counter",
            ]
        )
        for tier in ("redis_hit", "disk_hit", "miss"):
            lines.append(
                f'ecomreview_absa_cache_events_total{{tier="{tier}"}} {cache_ev.get(tier, 0)}'
            )

        lines.extend(
            [
                "# HELP ecomreview_llm_fallback_total Fallback activations to B1RuleAnalyzer.",
                "# TYPE ecomreview_llm_fallback_total counter",
            ]
        )
        if not fallbacks:
            lines.append('ecomreview_llm_fallback_total{scenario="global"} 0')
        else:
            for stag, val in sorted(fallbacks.items()):
                lines.append(f'ecomreview_llm_fallback_total{{scenario="{stag}"}} {val}')

        if redis_client is not None:
            lines.extend(
                [
                    "# HELP ecomreview_rq_queue_length Current pending jobs in RQ priority queues.",
                    "# TYPE ecomreview_rq_queue_length gauge",
                ]
            )
            for qname in ("ecomreview_critical", "ecomreview_default", "ecomreview_low"):
                try:
                    qlen = int(redis_client.llen(f"rq:queue:{qname}") or 0)
                except Exception:
                    qlen = -1
                lines.append(f'ecomreview_rq_queue_length{{queue="{qname}"}} {qlen}')

        return "\n".join(lines) + "\n"


metrics_registry = MetricsRegistry()


def _scrub_sentry_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """Scrub Vietnamese PII from Sentry payloads before sending externally."""
    try:
        msg = event.get("message")
        if isinstance(msg, str):
            event["message"] = scrub_pii(msg)
        exc_vals = (event.get("exception") or {}).get("values") or []
        for item in exc_vals:
            if isinstance(item, dict) and isinstance(item.get("value"), str):
                item["value"] = scrub_pii(item["value"])
    except Exception:
        pass
    return event


def init_sentry_if_configured() -> bool:
    """Initialize Sentry SDK when SENTRY_DSN is set; returns True if active."""
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("ECOMREVIEW_ENV", "development").strip().lower(),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            before_send=_scrub_sentry_event,
        )
        return True
    except ImportError:
        logger.warning("SENTRY_DSN is set but sentry-sdk is not installed; skipping Sentry init.")
        return False
    except Exception as exc:
        logger.warning("Sentry initialization failed: %s", exc)
        return False


# CreBy: MenBoyBMN
