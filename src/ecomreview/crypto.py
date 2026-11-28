"""Symmetric encryption-at-rest utilities for Shop secrets and credentials.

Uses cryptography MultiFernet (AES-128-CBC + HMAC-SHA256) with key rotation support
via comma-separated Fernet keys in `ECOMREVIEW_ENCRYPTION_KEY`.
"""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from ecomreview.api.auth import is_production_env

ENCRYPTED_PREFIX = "enc:v1:"

_DEV_FALLBACK_KEY = Fernet.generate_key().decode("ascii")


def get_encryption_keys() -> list[bytes]:
    """Return validated Fernet key(s); fail closed in production when missing/invalid."""
    raw = os.getenv("ECOMREVIEW_ENCRYPTION_KEY", "").strip()
    if raw:
        keys: list[bytes] = []
        for part in raw.split(","):
            cand = part.strip()
            if not cand:
                continue
            try:
                key_bytes = cand.encode("utf-8")
                Fernet(key_bytes)
            except Exception as exc:
                raise RuntimeError(
                    "ECOMREVIEW_ENCRYPTION_KEY must contain valid Fernet base64 key(s)."
                ) from exc
            keys.append(key_bytes)
        if not keys:
            raise RuntimeError("ECOMREVIEW_ENCRYPTION_KEY must contain valid Fernet base64 key(s).")
        return keys

    if is_production_env():
        raise RuntimeError("ECOMREVIEW_ENCRYPTION_KEY is required when ECOMREVIEW_ENV=production.")
    return [_DEV_FALLBACK_KEY.encode("ascii")]


def get_fernet() -> MultiFernet:
    """Return a MultiFernet instance supporting seamless key rotation."""
    return MultiFernet([Fernet(k) for k in get_encryption_keys()])


def is_encrypted_secret(value: str | None) -> bool:
    """Return True when the stored secret already carries the encryption prefix."""
    return bool(value and value.startswith(ENCRYPTED_PREFIX))


def encrypt_secret(plaintext: str | None) -> str:
    """Encrypt a plaintext secret idempotently; returns '' for empty values."""
    if not plaintext:
        return ""
    if is_encrypted_secret(plaintext):
        return plaintext
    token = get_fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_secret(stored: str | None) -> str:
    """Decrypt an encrypted secret; passes through legacy unencrypted values."""
    if not stored:
        return ""
    if not is_encrypted_secret(stored):
        return stored
    raw_token = stored[len(ENCRYPTED_PREFIX) :]
    try:
        return get_fernet().decrypt(raw_token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError(
            "Failed to decrypt stored secret; check ECOMREVIEW_ENCRYPTION_KEY."
        ) from exc


# CreBy: MenBoyBMN
