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


class WebhookReplayGuard:
    """Replay-protection nonce/signature cache backed by Redis with in-memory fallback."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seen: dict[str, float] = {}

    def check_and_mark(self, key: str, ttl_seconds: int = 600) -> bool:
        """Return True if key is unseen and mark it; return False if replayed."""
        r_client = rate_limiter._get_redis()
        if r_client is not None:
            try:
                was_set = r_client.set(f"ecomreview:wh_replay:{key}", "1", nx=True, ex=ttl_seconds)
                return bool(was_set)
            except Exception as exc:
                logger.debug("Redis replay guard failed, falling back to memory: %s", exc)

        now = time.monotonic()
        with self._lock:
            expired = [k for k, exp_ts in self._seen.items() if exp_ts <= now]
            for k in expired:
                del self._seen[k]
            if key in self._seen:
                return False
            self._seen[key] = now + ttl_seconds
            return True

    def reset(self) -> None:
        """Clear in-memory replay cache (used in tests)."""
        with self._lock:
            self._seen.clear()


webhook_replay_guard = WebhookReplayGuard()


class AccountLockoutGuard:
    """Per-email brute-force lockout guard backed by Redis with in-memory fallback."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._failures: dict[str, deque[float]] = {}
        self._locked_until: dict[str, float] = {}

    @staticmethod
    def _norm(email: str) -> str:
        return (email or "").strip().lower()

    def is_locked(self, email: str) -> int:
        """Return remaining lock seconds (> 0) if the email is currently locked out."""
        key = self._norm(email)
        if not key:
            return 0
        r_client = rate_limiter._get_redis()
        if r_client is not None:
            try:
                ttl = r_client.ttl(f"ecomreview:lock:{key}")
                return int(ttl) if ttl and int(ttl) > 0 else 0
            except Exception as exc:
                logger.debug("Redis lockout check failed, falling back to memory: %s", exc)

        now = time.monotonic()
        with self._lock:
            until = self._locked_until.get(key, 0.0)
            if until > now:
                return int(until - now) + 1
            self._locked_until.pop(key, None)
            return 0

    def record_failure(
        self,
        email: str,
        max_failures: int = 5,
        window_seconds: int = 600,
        lock_seconds: int = 600,
    ) -> bool:
        """Record a failed login attempt; returns True if account is now locked."""
        key = self._norm(email)
        if not key:
            return False
        r_client = rate_limiter._get_redis()
        if r_client is not None:
            try:
                fail_key = f"ecomreview:fail:{key}"
                count = r_client.incr(fail_key)
                if count == 1:
                    r_client.expire(fail_key, window_seconds)
                if int(count) >= max_failures:
                    r_client.set(f"ecomreview:lock:{key}", "1", ex=lock_seconds)
                    return True
                return False
            except Exception as exc:
                logger.debug("Redis lockout write failed, falling back to memory: %s", exc)

        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            q = self._failures.setdefault(key, deque())
            while q and q[0] < cutoff:
                q.popleft()
            q.append(now)
            if len(q) >= max_failures:
                self._locked_until[key] = now + lock_seconds
                return True
            return False

    def clear(self, email: str) -> None:
        """Reset failure counters and unlock account on successful login."""
        key = self._norm(email)
        if not key:
            return
        r_client = rate_limiter._get_redis()
        if r_client is not None:
            try:
                r_client.delete(f"ecomreview:fail:{key}", f"ecomreview:lock:{key}")
            except Exception as exc:
                logger.debug("Redis lockout clear failed: %s", exc)
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)

    def reset(self) -> None:
        """Clear all in-memory lockout state (used in tests)."""
        with self._lock:
            self._failures.clear()
            self._locked_until.clear()


account_lockout = AccountLockoutGuard()


class TenantJobQuotaGuard:
    """Per-shop background job quota guard to prevent noisy-neighbor saturation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[str, deque[float]] = {}

    def check(
        self,
        scenario_tag: str,
        max_jobs: int | None = None,
        window_seconds: int = 60,
    ) -> None:
        """Enforce per-tenant background job rate limit; raises HTTP 429 when exceeded."""
        if os.getenv("ECOMREVIEW_RATE_LIMIT_DISABLE", "false").strip().lower() == "true":
            return
        if max_jobs is None:
            raw = os.getenv("ECOMREVIEW_TENANT_MAX_JOBS_PER_MIN", "").strip()
            limit = int(raw) if raw.isdigit() else 15
        else:
            limit = max(1, int(max_jobs))
        key = (scenario_tag or "default").strip().lower()

        r_client = rate_limiter._get_redis()
        if r_client is not None:
            try:
                now_bucket = int(time.time() // window_seconds)
                rkey = f"ecomreview:tenant_jq:{key}:{now_bucket}"
                cnt = r_client.incr(rkey)
                if cnt == 1:
                    r_client.expire(rkey, window_seconds + 5)
                if int(cnt) > limit:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=(
                            f"Gian hàng '{scenario_tag}' đang có quá nhiều tác vụ chạy đồng thời. "
                            "Vui lòng thử lại sau ít phút."
                        ),
                    )
                return
            except HTTPException:
                raise
            except Exception as exc:
                logger.debug("Redis tenant quota check failed, falling back to memory: %s", exc)

        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            q = self._buckets.setdefault(key, deque())
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Gian hàng '{scenario_tag}' đang có quá nhiều tác vụ chạy đồng thời. "
                        "Vui lòng thử lại sau ít phút."
                    ),
                )
            q.append(now)

    def reset(self) -> None:
        """Clear in-memory tenant job counters (used in tests)."""
        with self._lock:
            self._buckets.clear()


tenant_job_quota = TenantJobQuotaGuard()


def client_ip_from_request(request: Request) -> str:
    """Extract client IP respecting X-Forwarded-For behind Nginx."""
    xff = request.headers.get("x-forwarded-for", "").strip()
    if xff:
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


# CreBy: MenBoyBMN
