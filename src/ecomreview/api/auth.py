"""JWT authentication and PBKDF2 password hashing utilities for EcomReview AI Pilot."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "ecomreview_session"
JWT_ALGORITHM = "HS256"
DEFAULT_TOKEN_EXPIRE_MINUTES = 720  # 12 hours
PBKDF2_ITERATIONS = 310_000
MIN_PROD_SECRET_LEN = 32

_DEV_FALLBACK_SECRET = secrets.token_hex(32)


def is_production_env() -> bool:
    """Return True when ECOMREVIEW_ENV is explicitly set to 'production'."""
    return os.getenv("ECOMREVIEW_ENV", "development").strip().lower() == "production"


def get_jwt_secret() -> str:
    """Return signing secret for JWT; enforces strong secret in production."""
    secret = os.getenv("ECOMREVIEW_JWT_SECRET", "").strip()
    if secret:
        if is_production_env() and len(secret) < MIN_PROD_SECRET_LEN:
            raise RuntimeError(
                f"ECOMREVIEW_JWT_SECRET must be at least {MIN_PROD_SECRET_LEN} characters "
                "when ECOMREVIEW_ENV=production."
            )
        return secret

    if is_production_env():
        raise RuntimeError("ECOMREVIEW_JWT_SECRET is required when ECOMREVIEW_ENV=production.")
    return _DEV_FALLBACK_SECRET


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using PBKDF2-HMAC-SHA256 with a random 16-byte salt."""
    if not plain_password or len(plain_password) < 6:
        raise ValueError("Password must be at least 6 characters long.")
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(plain_password: str, encoded_hash: str) -> bool:
    """Verify a plaintext password against a stored PBKDF2-HMAC-SHA256 hash."""
    if not plain_password or not encoded_hash:
        return False
    try:
        scheme, iter_str, salt, expected_hex = encoded_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iter_str)
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return hmac.compare_digest(dk.hex(), expected_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(
    user: dict[str, Any],
    expires_minutes: int | None = None,
) -> str:
    """Create a signed HS256 JWT access token for an authenticated user."""
    ttl = (
        expires_minutes
        if expires_minutes is not None
        else int(os.getenv("ECOMREVIEW_JWT_EXPIRE_MINUTES", str(DEFAULT_TOKEN_EXPIRE_MINUTES)))
    )
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "email": str(user["email"]),
        "name": str(user.get("full_name") or user["email"]),
        "role": str(user.get("role") or "owner").lower(),
        "allowed_shops": list(user.get("allowed_shops") or []),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=max(5, ttl))).timestamp()),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed HS256 JWT access token."""
    return jwt.decode(
        token,
        get_jwt_secret(),
        algorithms=[JWT_ALGORITHM],
        options={"require": ["sub", "email", "role", "exp"]},
    )


# CreBy: MenBoyBMN
