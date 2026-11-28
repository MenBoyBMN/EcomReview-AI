"""Shared Redis + Atomic Disk ABSA analysis cache store for multi-worker deployments."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from ecomreview.api.metrics import metrics_registry

logger = logging.getLogger(__name__)

DEFAULT_CACHE_TTL_SEC = 7 * 86400  # 7 days


def _resolve_ttl_seconds(ttl_sec: int | None) -> int:
    if ttl_sec is not None:
        return max(60, int(ttl_sec))
    raw = os.getenv("ECOMREVIEW_LLM_CACHE_TTL_SEC", "").strip()
    if raw.isdigit():
        return max(60, int(raw))
    return DEFAULT_CACHE_TTL_SEC


class ABSAAnalysisCache:
    """Two-tier SHA-256 analysis cache backed by Redis with atomic local disk fallback."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        redis_client: Any = None,
        ttl_sec: int | None = None,
    ) -> None:
        self.cache_dir = cache_dir
        self.ttl_sec = _resolve_ttl_seconds(ttl_sec)
        self._lock = threading.Lock()
        self._redis_client = redis_client
        self._redis_checked = redis_client is not None
        self.hits_redis = 0
        self.hits_disk = 0
        self.misses = 0

    def _get_redis(self) -> Any:
        if self._redis_checked:
            return self._redis_client
        with self._lock:
            if self._redis_checked:
                return self._redis_client
            self._redis_checked = True
            if os.getenv("ECOMREVIEW_REDIS_CACHE_DISABLE", "false").strip().lower() == "true":
                return None
            redis_url = os.getenv("REDIS_URL", "").strip()
            if not redis_url:
                return None
            try:
                import redis

                client = redis.Redis.from_url(
                    redis_url,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                    decode_responses=True,
                )
                client.ping()
                self._redis_client = client
            except Exception as exc:
                logger.debug("Redis unavailable for ABSA cache, using disk fallback: %s", exc)
                self._redis_client = None
            return self._redis_client

    def get(self, cache_key: str) -> dict[str, Any] | None:
        """Fetch cached ABSA dict by SHA-256 key from Redis or fallback local disk."""
        r_client = self._get_redis()
        redis_key = f"ecomreview:absa:{cache_key}"
        if r_client is not None:
            try:
                raw = r_client.get(redis_key)
                if raw:
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8")
                    data = json.loads(raw)
                    with self._lock:
                        self.hits_redis += 1
                    metrics_registry.inc_cache_event("redis_hit")
                    return data
            except Exception as exc:
                logger.debug("Redis cache read failed for %s: %s", cache_key[:12], exc)

        if self.cache_dir is not None:
            cand_file = self.cache_dir / f"gemini_{cache_key}.json"
            if cand_file.exists():
                try:
                    data = json.loads(cand_file.read_text(encoding="utf-8"))
                    with self._lock:
                        self.hits_disk += 1
                    metrics_registry.inc_cache_event("disk_hit")
                    if r_client is not None:
                        try:
                            r_client.set(
                                redis_key,
                                json.dumps(data, ensure_ascii=False),
                                ex=self.ttl_sec,
                            )
                        except Exception:
                            pass
                    return data
                except Exception as exc:
                    logger.warning("Disk cache read failed for key %s: %s.", cache_key, exc)

        with self._lock:
            self.misses += 1
        metrics_registry.inc_cache_event("miss")
        return None

    def set(self, cache_key: str, payload: dict[str, Any]) -> None:
        """Persist ABSA dict to Redis (shared) and atomic disk cache when enabled."""
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        r_client = self._get_redis()
        if r_client is not None:
            try:
                r_client.set(f"ecomreview:absa:{cache_key}", serialized, ex=self.ttl_sec)
            except Exception as exc:
                logger.debug("Redis cache write failed for %s: %s", cache_key[:12], exc)

        demo_mode = os.getenv("DEMO_CACHE_MODE", "true").strip().lower() != "false"
        if self.cache_dir is not None and (demo_mode or r_client is None):
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                target = self.cache_dir / f"gemini_{cache_key}.json"
                tmp_path = self.cache_dir / f"gemini_{cache_key}.tmp.{threading.get_ident()}"
                tmp_path.write_text(serialized, encoding="utf-8")
                os.replace(tmp_path, target)
            except OSError as exc:
                logger.debug("Disk cache write skipped/failed for %s: %s", cache_key[:12], exc)

    def stats(self) -> dict[str, int]:
        """Return cache hit/miss counters for observability."""
        with self._lock:
            return {
                "hits_redis": self.hits_redis,
                "hits_disk": self.hits_disk,
                "misses": self.misses,
            }


# CreBy: MenBoyBMN
