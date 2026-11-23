"""Structured JSON logging and X-Request-ID middleware for Production observability."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("ecomreview.http")


class JsonLogFormatter(logging.Formatter):
    """Formats log records as single-line JSON for log aggregation tools."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for attr in ("request_id", "method", "path", "status_code", "duration_ms", "user"):
            val = getattr(record, attr, None)
            if val is not None:
                payload[attr] = val
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Configure structured JSON logging when ECOMREVIEW_LOG_JSON=true or in production."""
    use_json = (
        os.getenv("ECOMREVIEW_LOG_JSON", "").strip().lower() == "true"
        or os.getenv("ECOMREVIEW_ENV", "development").strip().lower() == "production"
    )
    level_name = os.getenv("ECOMREVIEW_LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    if use_json:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter())
        root_logger.handlers = [handler]


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach X-Request-ID header and log structured access metrics."""

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = req_id
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
        response.headers["X-Request-ID"] = req_id

        principal = getattr(request.state, "principal", None)
        user_email = getattr(principal, "email", "-") if principal else "-"
        logger.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "user": user_email,
            },
        )
        return response


# CreBy: MenBoyBMN
