"""Lightweight sliding-window rate limiter (Redis-backed with in-memory fallback)."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """Per-key sliding-window rate limiter safe for Pilot deployments."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[str, deque[float]] = {}
        self._redis_client = None
        self._redis_checked = False

    def _get_redis(self):
        if self._redis_checked:
            return self._redis_client
        self._redis_checked = True
        redis_url = os.getenv("REDIS_URL", "").strip()
        if not redis_url:
            return None
        try:
            import redis

            client = redis.Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
            client.ping()
            self._redis_client = client
        except Exception as exc:
            logger.debug("Redis unavailable for rate limiter, using in-memory fallback: %s", exc)
            self._redis_client = None
        return self._redis_client

    def check(self, key: str, max_requests: int, window_seconds: int = 60) -> None:
        """Record a hit for key and raise HTTP 429 if limit is exceeded."""
        if os.getenv("ECOMREVIEW_RATE_LIMIT_DISABLE", "false").strip().lower() == "true":
            return

        r_client = self._get_redis()
        if r_client is not None:
            try:
                now_bucket = int(time.time() // window_seconds)
                rkey = f"ecomreview:rl:{key}:{now_bucket}"
                count = r_client.incr(rkey)
                if count == 1:
                    r_client.expire(rkey, window_seconds + 5)
                if count > max_requests:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút.",
                    )
                return
            except HTTPException:
                raise
            except Exception as exc:
                logger.debug("Redis rate limit failed, falling back to memory: %s", exc)

        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            q = self._buckets.setdefault(key, deque())
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút.",
                )
            q.append(now)

    def reset(self) -> None:
        """Clear in-memory buckets (used in tests)."""
        with self._lock:
            self._buckets.clear()


rate_limiter = SlidingWindowRateLimiter()


def client_ip_from_request(request: Request) -> str:
    """Extract client IP respecting X-Forwarded-For behind Nginx."""
    xff = request.headers.get("x-forwarded-for", "").strip()
    if xff:
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


# CreBy: MenBoyBMN
