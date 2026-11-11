"""API Security and Authentication dependencies for EcomReview AI."""

from __future__ import annotations

import os
import secrets

from fastapi import Header, HTTPException, status


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Enforce X-API-Key header authentication when ECOMREVIEW_API_KEY is configured.

    When ECOMREVIEW_API_KEY environment variable is empty or unset, authentication
    is bypassed (development/demo mode).

    Raises:
        HTTPException: 401 Unauthorized if key is required and invalid/missing.
    """
    expected_key = os.getenv("ECOMREVIEW_API_KEY", "").strip()
    if not expected_key:
        return

    if not x_api_key or not secrets.compare_digest(x_api_key.strip(), expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header.",
        )


def get_current_reviewer(
    x_reviewer: str | None = Header(default=None, alias="X-Reviewer"),
) -> str:
    """Extract reviewer name from X-Reviewer header for audit logging."""
    if x_reviewer and x_reviewer.strip():
        return x_reviewer.strip()
    return "shop_owner"


# CreBy: MenBoyBMN
